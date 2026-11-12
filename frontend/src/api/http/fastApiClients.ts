import type { GeoPoint, SafetyIndexValue, ScenarioSummary, Trip } from "../../domain/types";
import type { SafetyIndexClient, ScenariosClient } from "../clients";
import type { SafetyIndexRequestDto } from "../contracts";
import { parseSafetyIndexResponse, parseScenarioListResponse, parseScenarioResponse } from "../validation";

/*
 * Clients des API FastAPI : `services/routing` (scenarios) et `services/safety` (indice).
 */

const SAFETY_BATCH_SIZE = 5000;

async function readJson(response: Response, service: string): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`${service} service responded with HTTP ${response.status}`);
  }
  return response.json();
}

export class FastApiScenariosClient implements ScenariosClient {
  constructor(private readonly baseUrl: string) {}

  async listScenarios(signal?: AbortSignal): Promise<ScenarioSummary[]> {
    const response = await fetch(new URL("/scenarios", this.baseUrl), { signal });
    return parseScenarioListResponse(await readJson(response, "Routing"));
  }

  async fetchScenarioTrips(scenarioId: string, signal?: AbortSignal): Promise<Trip[]> {
    const url = new URL(`/scenarios/${encodeURIComponent(scenarioId)}`, this.baseUrl);
    const response = await fetch(url, { signal });
    return parseScenarioResponse(await readJson(response, "Routing"), scenarioId);
  }
}

export class FastApiSafetyIndexClient implements SafetyIndexClient {
  constructor(private readonly baseUrl: string) {}

  async fetchSafetyIndices(points: GeoPoint[], signal?: AbortSignal): Promise<SafetyIndexValue[]> {
    const results: SafetyIndexValue[] = [];
    for (let offset = 0; offset < points.length; offset += SAFETY_BATCH_SIZE) {
      const batch = points.slice(offset, offset + SAFETY_BATCH_SIZE);
      const body: SafetyIndexRequestDto = { points: batch };
      const response = await fetch(new URL("/safety-index", this.baseUrl), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });
      results.push(...parseSafetyIndexResponse(await readJson(response, "Safety index"), batch.length));
    }
    return results;
  }
}
