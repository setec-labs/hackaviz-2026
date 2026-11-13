from math import fsum

from hackaviz_2026.journey_safety import (
    JourneySafetyRequest,
    JourneySafetyResponse,
    JourneySafetyResult,
)
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
from hackaviz_2026.routing import Journey, JourneyLeg

from safety.providers import IndicatorProvider, IndicatorUnavailableError
from safety.ridership import RidershipIndicatorProvider


class UnknownIndicatorError(ValueError):
    """A score request references an indicator that is not registered."""


class IndicatorNotImplementedError(RuntimeError):
    """A registered indicator cannot yet be evaluated."""


class IndicatorService:
    """Evaluate registered providers and aggregate their normalized scores."""

    def __init__(
        self,
        providers: tuple[IndicatorProvider, ...],
        ridership: RidershipIndicatorProvider | None = None,
    ) -> None:
        if not providers:
            raise ValueError("At least one indicator provider is required")
        self._providers = {provider.id: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ValueError("Indicator provider IDs must be unique")
        self._ridership = ridership

    def list_indicators(self) -> list[Indicator]:
        """Return metadata for registered indicators in provider order."""
        metadata = [
            Indicator(id=provider.id, name=provider.name, description=provider.description)
            for provider in self._providers.values()
        ]
        if self._ridership is not None:
            metadata.append(Indicator(
                id=self._ridership.id, name=self._ridership.name,
                description=self._ridership.description,
            ))
        return metadata

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
            raise UnknownIndicatorError(
                f"Unknown position indicator IDs: {', '.join(unknown)}. "
                "Use /journey-safety for contextual transit indicators."
            )
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

    async def _leg_values(self, journey: Journey, leg: JourneyLeg) -> list[float | None]:
        start, end = leg.point_range
        if leg.mode == "transit":
            if self._ridership is None:
                raise IndicatorNotImplementedError("Ridership provider is not configured")
            try:
                return [await self._ridership.evaluate_arc(leg)] * (end - start)
            except IndicatorUnavailableError:
                return [None] * (end - start)
        provider = self._providers.get("lighting")
        if provider is None:
            raise IndicatorNotImplementedError("Lighting provider is not configured")
        values = []
        for longitude, latitude in journey.coordinates[start:end]:
            try:
                result = await self._evaluate(
                    Position(longitude=longitude, latitude=latitude), [provider],
                )
                values.append(result[0].value)
            except IndicatorUnavailableError:
                values.append(None)
        return values

    async def journey_safety(self, request: JourneySafetyRequest) -> JourneySafetyResponse:
        """Keep local indicators distinct and combine duration means at journey level."""
        results = []
        for journey in request.journeys:
            values: list[float | None] = [None] * len(journey.coordinates)
            totals: dict[str, list[tuple[float, float]]] = {"lighting": [], "ridership": []}
            missing: set[str] = set()
            applicable: set[str] = set()
            for leg in journey.legs:
                indicator_id = "ridership" if leg.mode == "transit" else "lighting"
                duration = (leg.end_time - leg.start_time).total_seconds()
                if duration > 0:
                    applicable.add(indicator_id)
                start, end = leg.point_range
                leg_values = await self._leg_values(journey, leg)
                values[start:end] = leg_values
                if duration <= 0:
                    continue
                if any(value is None for value in leg_values):
                    missing.add(indicator_id)
                    continue
                known = [value for value in leg_values if value is not None]
                # Integrate the sampled field in time, extending endpoint values to leg boundaries.
                offset_start = (leg.start_time - journey.start_time).total_seconds()
                times = [0.0] + [
                    min(duration, max(0.0, offset - offset_start))
                    for offset in journey.offsets_s[start:end]
                ] + [duration]
                samples = [known[0], *known, known[-1]]
                intervals = [right - left for left, right in zip(times, times[1:])]
                mean = fsum(
                    interval * ((a + b) / 2)
                    for interval, a, b in zip(intervals, samples, samples[1:])
                ) / fsum(intervals)
                totals[indicator_id].append((mean, duration))
            indicators = [
                IndicatorResult(
                    indicator_id=key,
                    value=fsum(value * duration for value, duration in parts)
                    / fsum(duration for _, duration in parts),
                )
                for key, parts in totals.items() if parts and key not in missing
            ]
            weights = {"lighting": request.weights.lighting, "ridership": request.weights.ridership}
            active = [key for key in applicable if weights[key] > 0]
            weight_sum = fsum(weights[key] for key in active)
            score = None
            if weight_sum and not missing.intersection(active):
                score = fsum(
                    indicator.value * weights[indicator.indicator_id]
                    for indicator in indicators
                ) / weight_sum
            results.append(JourneySafetyResult(
                journey_id=journey.journey_id, values=values, score=score, indicators=indicators,
            ))
        return JourneySafetyResponse(journeys=results, weights=request.weights)
