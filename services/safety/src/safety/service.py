from math import fsum

from hackaviz_2026.models import (
    EvaluateResponse,
    Indicator,
    IndicatorResult,
    Position,
    ScoreRequest,
    ScoreResponse,
)

from safety.providers import IndicatorProvider


class UnknownIndicatorError(ValueError):
    pass


class IndicatorNotImplementedError(RuntimeError):
    pass


class IndicatorService:
    def __init__(self, providers: tuple[IndicatorProvider, ...]) -> None:
        self._providers = {provider.id: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ValueError("Indicator provider IDs must be unique")

    def list_indicators(self) -> list[Indicator]:
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
        indicators = await self._evaluate(position, list(self._providers.values()))
        return EvaluateResponse(position=position, indicators=indicators)

    async def score(self, request: ScoreRequest) -> ScoreResponse:
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
