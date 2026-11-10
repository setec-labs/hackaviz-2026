import type { AppConfig } from "../config";
import { MockSafetyIndexClient, MockTripsClient } from "../mocks/mockClients";
import type { DataClients } from "./clients";
import { FastApiSafetyIndexClient, FastApiTripsClient } from "./http/fastApiClients";

/** Seul endroit ou l'on choisit entre donnees simulees et API FastAPI. */
export function createDataClients(config: AppConfig): DataClients {
  if (config.dataSource === "api") {
    return {
      trips: new FastApiTripsClient(config.tripsApiUrl),
      safety: new FastApiSafetyIndexClient(config.safetyApiUrl),
      isSimulated: false,
    };
  }
  const { tripCount, seed, latencyMs, failure } = config.mock;
  return {
    trips: new MockTripsClient({ tripCount, seed, latencyMs, fail: failure === "trips" }),
    safety: new MockSafetyIndexClient({ tripCount, seed, latencyMs, fail: failure === "safety" }),
    isSimulated: true,
  };
}
