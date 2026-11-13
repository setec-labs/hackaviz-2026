import type { GeoPoint, SafetyIndexValue, ScenarioSummary, Trip } from "../domain/types";
import type { JourneySafetyResultDto, SafetyWeights } from "./contracts";

/**
 * Scenario data access implemented by both mock and FastAPI clients.
 */
export interface ScenariosClient {
  /** List the scenarios used to display clickable origin points. */
  listScenarios(signal?: AbortSignal): Promise<ScenarioSummary[]>;
  /** Load the journeys belonging to a scenario. */
  fetchScenarioTrips(scenarioId: string, signal?: AbortSignal): Promise<Trip[]>;
}

/** Provides one normalized safety index per input position. */
export interface SafetyIndexClient {
  /**
   * Return indices in the same order and with the same length as `points`.
   * A null value means that an indicator is unavailable at that position.
   */
  fetchSafetyIndices(points: GeoPoint[], signal?: AbortSignal): Promise<SafetyIndexValue[]>;
  /** Contextual local values and server-computed weighted global scores. */
  fetchJourneySafety(trips: Trip[], weights: SafetyWeights, signal?: AbortSignal): Promise<JourneySafetyResultDto[]>;
}

/** Data sources and flags identifying which sources are simulated. */
export interface DataClients {
  scenarios: ScenariosClient;
  safety: SafetyIndexClient;
  /** Whether the displayed scenarios and journeys are simulated. */
  tripsSimulated: boolean;
  /** Whether the safety index is simulated. */
  safetySimulated: boolean;
}
