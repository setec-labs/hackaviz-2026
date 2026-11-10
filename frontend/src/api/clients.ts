import type { GeoPoint, SafetyIndexValue, Trip } from "../domain/types";

/**
 * Point d'entree unique de l'application vers les donnees.
 * Implemente par les mocks (`src/mocks/`) et par les clients FastAPI (`src/api/http/`).
 */
export interface TripsClient {
  /** API 1 : liste des trajets a partir d'une position geographique. */
  fetchTrips(origin: GeoPoint, signal?: AbortSignal): Promise<Trip[]>;
}

export interface SafetyIndexClient {
  /**
   * API 2 : indice lie au sentiment de securite pour chaque position.
   * Le resultat a la meme longueur et le meme ordre que `points`.
   */
  fetchSafetyIndices(points: GeoPoint[], signal?: AbortSignal): Promise<SafetyIndexValue[]>;
}

export interface DataClients {
  trips: TripsClient;
  safety: SafetyIndexClient;
  /** Indique a l'interface que les donnees affichees sont simulees. */
  isSimulated: boolean;
}
