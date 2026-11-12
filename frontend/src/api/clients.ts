import type { GeoPoint, SafetyIndexValue, ScenarioSummary, Trip } from "../domain/types";

/**
 * Point d'entree unique de l'application vers les donnees.
 * Implemente par les mocks (`src/mocks/`) et par les clients FastAPI (`src/api/http/`).
 */
export interface ScenariosClient {
  /** API 1 : catalogue des scenarios (points de depart cliquables). */
  listScenarios(signal?: AbortSignal): Promise<ScenarioSummary[]>;
  /** API 1 : trajets d'un scenario. */
  fetchScenarioTrips(scenarioId: string, signal?: AbortSignal): Promise<Trip[]>;
}

export interface SafetyIndexClient {
  /**
   * API 2 : indice lie au sentiment de securite pour chaque position.
   * Le resultat a la meme longueur et le meme ordre que `points`.
   */
  fetchSafetyIndices(points: GeoPoint[], signal?: AbortSignal): Promise<SafetyIndexValue[]>;
}

export interface DataClients {
  scenarios: ScenariosClient;
  safety: SafetyIndexClient;
  /** Indique a l'interface que les scenarios et trajets affiches sont simules. */
  tripsSimulated: boolean;
  /** Indique a l'interface que l'indice de securite est simule. */
  safetySimulated: boolean;
}
