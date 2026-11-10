from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator


NormalizedScore = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


class Position(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float = Field(ge=-180.0, le=180.0, allow_inf_nan=False)


class Indicator(BaseModel):
    id: str
    name: str
    description: str


class IndicatorResult(BaseModel):
    indicator_id: str
    value: NormalizedScore


class EvaluateRequest(BaseModel):
    position: Position


class EvaluateResponse(BaseModel):
    position: Position
    indicators: list[IndicatorResult]


class IndicatorWeight(BaseModel):
    indicator_id: str
    weight: float = Field(ge=0.0, allow_inf_nan=False)


class ScoreRequest(BaseModel):
    position: Position
    weights: list[IndicatorWeight]

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        ids = [weight.indicator_id for weight in self.weights]
        if len(set(ids)) != len(ids):
            raise ValueError("Indicator weights must not contain duplicate IDs")
        if not any(weight.weight > 0 for weight in self.weights):
            raise ValueError("At least one indicator weight must be positive")
        return self


class ScoreResponse(BaseModel):
    position: Position
    score: NormalizedScore
    indicators: list[IndicatorResult]
