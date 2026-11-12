import type { AppConfig } from "../config";
import { MockSafetyIndexClient, MockTripsClient } from "../mocks/mockClients";
import type { DataClients } from "./clients";
import { FastApiSafetyIndexClient, FastApiTripsClient } from "./http/fastApiClients";

/** Seul endroit ou l'on choisit entre donnees simulees et API FastAPI, source par source. */
export function createDataClients(config: AppConfig): DataClients {
  const { tripCount, seed, latencyMs, failure } = config.mock;
  const tripsSimulated = config.dataSource === "mock";
  const safetySimulated = config.safetySource === "mock";
  return {
    trips: tripsSimulated
      ? new MockTripsClient({ tripCount, seed, latencyMs, fail: failure === "trips" })
      : new FastApiTripsClient(config.tripsApiUrl),
    safety: safetySimulated
      ? new MockSafetyIndexClient({ tripCount, seed, latencyMs, fail: failure === "safety" })
      : new FastApiSafetyIndexClient(config.safetyApiUrl),
    tripsSimulated,
    safetySimulated,
  };
}
