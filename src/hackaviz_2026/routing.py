from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from hackaviz_2026.models import NormalizedScore, Position


ScenarioId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=128)]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0, allow_inf_nan=False)]
Latitude = Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)]
Coordinate = tuple[Longitude, Latitude]
OffsetSeconds = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
PointIndex = Annotated[int, Field(ge=0, strict=True)]
JourneyMode = Literal["walk_access", "walk_egress", "walk_transfer", "wait", "transit"]


class Destination(Position):
    name: NonEmptyString


class JourneyLeg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: JourneyMode
    start_time: AwareDatetime
    end_time: AwareDatetime
    from_stop: NonEmptyString
    to_stop: NonEmptyString
    gtfs_trip_id: NonEmptyString | None = None
    point_range: tuple[PointIndex, PointIndex]

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("Leg end_time must not precede start_time")
        if self.point_range[0] >= self.point_range[1]:
            raise ValueError("Leg point_range must be a non-empty half-open interval")
        return self


class Journey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    journey_id: NonEmptyString
    destination: Destination
    start_time: AwareDatetime
    end_time: AwareDatetime
    legs: list[JourneyLeg] = Field(min_length=1)
    coordinates: list[Coordinate] = Field(min_length=1)
    offsets_s: list[OffsetSeconds] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timeline(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("Journey end_time must not precede start_time")
        if len(self.coordinates) != len(self.offsets_s):
            raise ValueError("Each coordinate must have exactly one offset")
        if self.offsets_s[0] != 0:
            raise ValueError("The first offset must be zero")
        if any(right < left for left, right in zip(self.offsets_s, self.offsets_s[1:])):
            raise ValueError("Offsets must be non-decreasing")
        point_index = 0
        leg_start = self.start_time
        for leg in self.legs:
            if leg.point_range[0] != point_index or leg.point_range[1] > len(self.coordinates):
                raise ValueError("Leg point ranges must partition the coordinates in order")
            if leg.start_time != leg_start:
                raise ValueError("Leg times must cover the journey without gaps or overlaps")
            point_index = leg.point_range[1]
            leg_start = leg.end_time
        if point_index != len(self.coordinates) or leg_start != self.end_time:
            raise ValueError("Legs must cover the full journey")
        return self


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ScenarioId
    name: NonEmptyString
    description: NonEmptyString
    type: NonEmptyString


class Scenario(ScenarioSummary):
    origin: Position
    departure_time: AwareDatetime
    journey: Journey

    @model_validator(mode="after")
    def validate_departure(self) -> Self:
        if self.journey.start_time < self.departure_time:
            raise ValueError("Journey must not start before the scenario departure_time")
        return self


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Scenario


class ReportResponse(BaseModel):
    scenario_id: ScenarioId
    position: Position
    person_count: int = Field(ge=0, strict=True)
    anxiety_index: NormalizedScore = Field(
        description="Normalized favorability score: 0 is least favorable, 1 most favorable."
    )
