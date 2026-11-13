from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator


NormalizedScore = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


class Position(BaseModel):
    """A WGS84 position expressed in degrees.

    Attributes:
        latitude: Latitude in the inclusive range [-90, 90].
        longitude: Longitude in the inclusive range [-180, 180].
    """

    latitude: float = Field(ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float = Field(ge=-180.0, le=180.0, allow_inf_nan=False)


class Indicator(BaseModel):
    """Public metadata identifying an indicator provider."""

    id: str
    name: str
    description: str


class IndicatorResult(BaseModel):
    """A provider's normalized score, where 1 is the most favorable."""

    indicator_id: str
    value: NormalizedScore


class EvaluateRequest(BaseModel):
    """Request all indicators at one position."""

    position: Position


class EvaluateResponse(BaseModel):
    """Indicator results associated with the requested position."""

    position: Position
    indicators: list[IndicatorResult]


class IndicatorWeight(BaseModel):
    """A nonnegative, finite weight for one indicator."""

    indicator_id: str
    weight: float = Field(ge=0.0, allow_inf_nan=False)


class ScoreRequest(BaseModel):
    """Request a weighted score at one position.

    Indicator IDs must be unique and at least one weight must be positive.
    """

    position: Position
    weights: list[IndicatorWeight]

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        """Reject duplicate indicator IDs and an all-zero or empty weight list."""
        ids = [weight.indicator_id for weight in self.weights]
        if len(set(ids)) != len(ids):
            raise ValueError("Indicator weights must not contain duplicate IDs")
        if not any(weight.weight > 0 for weight in self.weights):
            raise ValueError("At least one indicator weight must be positive")
        return self


class ScoreResponse(BaseModel):
    """A normalized weighted score and its component indicator results."""

    position: Position
    score: NormalizedScore
    indicators: list[IndicatorResult]


# Mirrors the frontend batch contract (`frontend/src/api/contracts.ts`), which sends at most this many points.
MAX_SAFETY_INDEX_POINTS = 5000


class SafetyIndexRequest(BaseModel):
    """Request indices for up to ``MAX_SAFETY_INDEX_POINTS`` positions."""

    points: list[Position] = Field(max_length=MAX_SAFETY_INDEX_POINTS)


class PositionSafetyIndex(Position):
    """A position and its index, or ``None`` if an indicator has no data."""

    value: NormalizedScore | None = Field(
        description="Normalized index (1 is most favorable), or null when no data covers the position."
    )


class SafetyIndexResponse(BaseModel):
    """Batch indices in the same order as the requested positions."""

    indices: list[PositionSafetyIndex]
