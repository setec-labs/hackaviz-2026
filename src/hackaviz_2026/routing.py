from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from hackaviz_2026.models import NormalizedScore, Position


ScenarioId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=128)]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0, allow_inf_nan=False)]
Latitude = Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)]
Coordinate = tuple[Longitude, Latitude]
OffsetSeconds = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
PointIndex = Annotated[int, Field(ge=0, strict=True)]
JourneyMode = Literal["walk_access", "walk_egress", "walk_transfer", "walk_direct", "wait", "transit"]


class Destination(Position):
    name: NonEmptyString
    population: int | None = Field(default=None, ge=0, strict=True)


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


def _check_scenario_journeys(journeys: list[Journey], departure_time: datetime) -> None:
    journey_ids = [journey.journey_id for journey in journeys]
    if len(set(journey_ids)) != len(journey_ids):
        raise ValueError("Journey IDs must be unique within a scenario")
    if any(journey.start_time < departure_time for journey in journeys):
        raise ValueError("Journeys must not start before the scenario departure_time")


class ScenarioDocument(BaseModel):
    """Content of a `journeys.json` file produced by the routing pipeline (one file per scenario)."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString | None = None
    description: NonEmptyString | None = None
    origin: Position
    departure_time: AwareDatetime
    journeys: list[Journey] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_journeys(self) -> Self:
        _check_scenario_journeys(self.journeys, self.departure_time)
        return self


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ScenarioId
    name: NonEmptyString
    description: NonEmptyString
    metadata_generated: bool = Field(
        description="True when name and description were derived from the data because the file has none."
    )
    origin: Position
    departure_time: AwareDatetime
    journey_count: int = Field(ge=1, strict=True)


class Scenario(ScenarioSummary):
    journeys: list[Journey] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_journey_count(self) -> Self:
        if self.journey_count != len(self.journeys):
            raise ValueError("journey_count must match the number of journeys")
        _check_scenario_journeys(self.journeys, self.departure_time)
        return self


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: ScenarioId


class JourneyReport(BaseModel):
    journey_id: NonEmptyString
    position: Position = Field(description="Final point of the journey.")
    person_count: int = Field(ge=0, strict=True)
    anxiety_index: NormalizedScore = Field(
        description="Normalized favorability score: 0 is least favorable, 1 most favorable."
    )


class ReportResponse(BaseModel):
    scenario_id: ScenarioId
    journeys: list[JourneyReport]
