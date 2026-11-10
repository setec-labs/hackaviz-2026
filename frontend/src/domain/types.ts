/** Types du domaine utilises par l'application (independants du format des API). */

/** Position geographique en degres WGS84. */
export interface GeoPoint {
  latitude: number;
  longitude: number;
}

export interface Trip {
  id: string;
  /** Mode de deplacement s'il est fourni par l'API, sinon null. */
  mode: string | null;
  /** Debut et fin en millisecondes epoch UTC. */
  startTimeMs: number;
  endTimeMs: number;
  /** Positions ordonnees, au format deck.gl [longitude, latitude]. */
  path: [number, number][];
  /** Timestamp (ms epoch UTC) de chaque position, croissant. */
  timestampsMs: number[];
}

/**
 * Indice normalise lie au sentiment de securite, entre 0 et 1 (1 = contexte le plus favorable).
 * `null` signifie que l'indicateur n'est pas disponible pour cette position.
 * Il s'agit d'un indicateur, pas d'une mesure objective du danger.
 */
export type SafetyIndexValue = number | null;
