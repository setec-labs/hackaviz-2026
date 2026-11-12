/**
 * FastAPI JSON contracts mirroring the shared Pydantic models, using snake_case.
 * Routing models are defined in `src/hackaviz_2026/routing.py` and safety
 * models in `src/hackaviz_2026/models.py`.
 */

/** WGS84 position sent to or received from an API. */
export interface GeoPointDto {
  latitude: number;
  longitude: number;
}

/** A routing `GET /scenarios` result. */
export interface ScenarioSummaryDto {
  id: string;
  name: string;
  description: string;
  metadata_generated: boolean;
  origin: GeoPointDto;
  /** ISO 8601 departure time with a timezone. */
  departure_time: string;
  journey_count: number;
}

/** Named journey destination, with population when available. */
export interface DestinationDto extends GeoPointDto {
  name: string;
  population?: number | null;
}

/** A journey leg and the coordinate range it owns. */
export interface JourneyLegDto {
  /** One of `walk_access`, `walk_egress`, `walk_transfer`, `walk_direct`, `wait`, or `transit`. */
  mode: string;
  start_time: string;
  end_time: string;
  from_stop: string;
  to_stop: string;
  gtfs_trip_id: string | null;
  /** Half-open [start, end) index range in `coordinates`. */
  point_range: [number, number];
}

/** Routing journey with aligned coordinates and offsets. */
export interface JourneyDto {
  journey_id: string;
  destination: DestinationDto;
  start_time: string;
  end_time: string;
  legs: JourneyLegDto[];
  /** WGS84 positions as [longitude, latitude]. */
  coordinates: [number, number][];
  /** Seconds since `start_time`, one per coordinate. */
  offsets_s: number[];
}

/** Routing `GET /scenarios/{scenario_id}` response. */
export interface ScenarioDto extends ScenarioSummaryDto {
  journeys: JourneyDto[];
}

/** Safety `POST /safety-index` batch request. */
export interface SafetyIndexRequestDto {
  points: GeoPointDto[];
}

/** An index associated with a requested position. */
export interface SafetyIndexDto extends GeoPointDto {
  /** Normalized index in [0, 1], where 1 is most favorable, or null if unavailable. */
  value: number | null;
}

/** Indices in the same order as the requested positions. */
export interface SafetyIndexResponseDto {
  indices: SafetyIndexDto[];
}
