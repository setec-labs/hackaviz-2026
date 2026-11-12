import type { AppConfig } from "../config";
import { MockSafetyIndexClient, MockScenariosClient } from "../mocks/mockClients";
import type { DataClients } from "./clients";
import { FastApiSafetyIndexClient, FastApiScenariosClient } from "./http/fastApiClients";

/** Seul endroit ou l'on choisit entre donnees simulees et API FastAPI, source par source. */
export function createDataClients(config: AppConfig): DataClients {
  const { tripCount, seed, latencyMs, failure } = config.mock;
  const tripsSimulated = config.dataSource === "mock";
  const safetySimulated = config.safetySource === "mock";
  return {
    scenarios: tripsSimulated
      ? new MockScenariosClient({ tripCount, seed, latencyMs, fail: failure === "trips" })
      : new FastApiScenariosClient(config.tripsApiUrl),
    safety: safetySimulated
      ? new MockSafetyIndexClient({ tripCount, seed, latencyMs, fail: failure === "safety" })
      : new FastApiSafetyIndexClient(config.safetyApiUrl),
    tripsSimulated,
    safetySimulated,
  };
}
