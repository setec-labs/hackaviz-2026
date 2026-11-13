from math import fsum, isclose
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hackaviz_2026.models import MAX_SAFETY_INDEX_POINTS, IndicatorResult, NormalizedScore
from hackaviz_2026.routing import Journey


class SafetyWeights(BaseModel):
    """Relative importance of the two indicators, summing to one."""

    model_config = ConfigDict(extra="forbid")

    lighting: NormalizedScore = 0.5
    ridership: NormalizedScore = 0.5

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        if not isclose(fsum((self.lighting, self.ridership)), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("Indicator weights must sum to 1")
        return self


class JourneySafetyRequest(BaseModel):
    """Evaluate contextual indices and global scores for a bounded journey batch."""

    journeys: list[Journey] = Field(max_length=100)
    weights: SafetyWeights = Field(default_factory=SafetyWeights)

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        if sum(len(journey.coordinates) for journey in self.journeys) > MAX_SAFETY_INDEX_POINTS:
            raise ValueError(f"A batch must contain at most {MAX_SAFETY_INDEX_POINTS} coordinates")
        ids = [journey.journey_id for journey in self.journeys]
        if len(set(ids)) != len(ids):
            raise ValueError("Journey IDs must be unique within a batch")
        return self


class JourneySafetyResult(BaseModel):
    """Local values and a weighted global score; missing expected data stays null."""

    journey_id: str
    values: list[NormalizedScore | None]
    score: NormalizedScore | None
    indicators: list[IndicatorResult]


class JourneySafetyResponse(BaseModel):
    """Results in request order, with the effective configured weights."""

    journeys: list[JourneySafetyResult]
    weights: SafetyWeights
