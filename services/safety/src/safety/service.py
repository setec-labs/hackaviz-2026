from math import fsum

from hackaviz_2026.models import (
    EvaluateResponse,
    Indicator,
    IndicatorResult,
    Position,
    PositionSafetyIndex,
    ScoreRequest,
    ScoreResponse,
    SafetyIndexResponse,
)

from safety.providers import IndicatorProvider, IndicatorUnavailableError


class UnknownIndicatorError(ValueError):
    """A score request references an indicator that is not registered."""


class IndicatorNotImplementedError(RuntimeError):
    """A registered indicator cannot yet be evaluated."""


class IndicatorService:
    """Evaluate registered providers and aggregate their normalized scores."""

    def __init__(self, providers: tuple[IndicatorProvider, ...]) -> None:
        if not providers:
            raise ValueError("At least one indicator provider is required")
        self._providers = {provider.id: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ValueError("Indicator provider IDs must be unique")

    def list_indicators(self) -> list[Indicator]:
        """Return metadata for registered indicators in provider order."""
        return [
            Indicator(id=provider.id, name=provider.name, description=provider.description)
            for provider in self._providers.values()
        ]

    async def _evaluate(
        self, position: Position, providers: list[IndicatorProvider]
    ) -> list[IndicatorResult]:
        results = []
        for provider in providers:
            try:
                value = await provider.evaluate(position)
            except NotImplementedError as exc:
                raise IndicatorNotImplementedError(
                    f"Indicator '{provider.id}' is not implemented"
                ) from exc
            results.append(IndicatorResult(indicator_id=provider.id, value=value))
        return results

    async def evaluate(self, position: Position) -> EvaluateResponse:
        """Evaluate all registered indicators at one position."""
        indicators = await self._evaluate(position, list(self._providers.values()))
        return EvaluateResponse(position=position, indicators=indicators)

    async def score(self, request: ScoreRequest) -> ScoreResponse:
        """Evaluate requested indicators and calculate their weighted mean.

        Zero-weight indicators are still evaluated. Weights are scaled by the
        maximum before summation to avoid overflow.

        Args:
            request: Position and validated indicator weights.

        Returns:
            The normalized score and indicator results in request order.

        Raises:
            UnknownIndicatorError: A requested indicator ID is not registered.
            IndicatorNotImplementedError: A requested provider is unfinished.
            IndicatorUnavailableError: A provider has no data at the position.
        """
        weights = request.weights
        unknown = [
            weight.indicator_id
            for weight in weights
            if weight.indicator_id not in self._providers
        ]
        if unknown:
            raise UnknownIndicatorError(f"Unknown indicator IDs: {', '.join(unknown)}")
        providers = [self._providers[weight.indicator_id] for weight in weights]
        indicators = await self._evaluate(request.position, providers)
        max_weight = max(weight.weight for weight in weights)
        scaled_weights = [weight.weight / max_weight for weight in weights]
        total_weight = fsum(scaled_weights)
        score = fsum(
            result.value * weight
            for result, weight in zip(indicators, scaled_weights, strict=True)
        ) / total_weight
        return ScoreResponse(position=request.position, score=score, indicators=indicators)

    async def safety_index(self, positions: list[Position]) -> SafetyIndexResponse:
        """Evaluate an equal-weight index for each position.

        Args:
            positions: WGS84 positions to evaluate, in output order.

        Returns:
            An index per position; its value is ``None`` if any provider has no
            data there. Other provider failures are propagated.
        """
        providers = list(self._providers.values())
        indices = []
        for position in positions:
            try:
                results = await self._evaluate(position, providers)
            except IndicatorUnavailableError:
                value = None
            else:
                value = fsum(result.value for result in results) / len(results)
            indices.append(PositionSafetyIndex(
                latitude=position.latitude,
                longitude=position.longitude,
                value=value,
            ))
        return SafetyIndexResponse(indices=indices)
