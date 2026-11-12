/**
 * Contrats JSON des API FastAPI, refletant des modeles Pydantic (noms en snake_case).
 * - routing : `ScenarioSummary` / `Scenario` / `Journey` de `src/hackaviz_2026/routing.py` ;
 * - safety : `SafetyIndexRequest` / `SafetyIndexResponse` de `src/hackaviz_2026/models.py`.
 */

export interface GeoPointDto {
  latitude: number;
  longitude: number;
}

/** API 1 (routing) : element de `GET /scenarios`. */
export interface ScenarioSummaryDto {
  id: string;
  name: string;
  description: string;
  metadata_generated: boolean;
  origin: GeoPointDto;
  /** Date/heure ISO 8601 avec fuseau. */
  departure_time: string;
  journey_count: number;
}

export interface DestinationDto extends GeoPointDto {
  name: string;
  population?: number | null;
}

export interface JourneyLegDto {
  /** `walk_access`, `walk_egress`, `walk_transfer`, `walk_direct`, `wait`, `transit`. */
  mode: string;
  start_time: string;
  end_time: string;
  from_stop: string;
  to_stop: string;
  gtfs_trip_id: string | null;
  /** Intervalle semi-ouvert [debut, fin) d'indices dans `coordinates`. */
  point_range: [number, number];
}

export interface JourneyDto {
  journey_id: string;
  destination: DestinationDto;
  start_time: string;
  end_time: string;
  legs: JourneyLegDto[];
  /** Positions au format [longitude, latitude]. */
  coordinates: [number, number][];
  /** Secondes depuis `start_time`, une valeur par coordonnee. */
  offsets_s: number[];
}

/** API 1 (routing) : reponse de `GET /scenarios/{scenario_id}`. */
export interface ScenarioDto extends ScenarioSummaryDto {
  journeys: JourneyDto[];
}

/** API 2 (safety) : requete batch `POST /safety-index`. */
export interface SafetyIndexRequestDto {
  points: GeoPointDto[];
}

export interface SafetyIndexDto extends GeoPointDto {
  /** Indice dans [0, 1] (1 = plus favorable) ou null si non disponible. */
  value: number | null;
}

/** Les indices sont renvoyes dans le meme ordre que les points demandes. */
export interface SafetyIndexResponseDto {
  indices: SafetyIndexDto[];
}
