/**
 * Contrats JSON attendus des futures API FastAPI.
 * Ils refletent des modeles Pydantic (noms en snake_case) et sont PROVISOIRES :
 * a aligner avec les modeles partages de `src/hackaviz_2026/` lorsqu'ils seront definis.
 */

export interface GeoPointDto {
  latitude: number;
  longitude: number;
}

/** API 1 (routing) : position d'un trajet a un instant donne. */
export interface TripPointDto extends GeoPointDto {
  /** Date/heure ISO 8601 avec fuseau. */
  timestamp: string;
}

export interface TripDto {
  trip_id: string;
  start_time: string;
  end_time: string;
  mode?: string | null;
  points: TripPointDto[];
}

/** Reponse de `GET /trips?latitude=..&longitude=..`. */
export interface TripsResponseDto {
  origin: GeoPointDto;
  trips: TripDto[];
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
