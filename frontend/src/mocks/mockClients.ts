import type { SafetyIndexClient, ScenariosClient } from "../api/clients";
import type { JourneySafetyResultDto, SafetyWeights } from "../api/contracts";
import { parseSafetyIndexResponse, parseScenarioListResponse, parseScenarioResponse } from "../api/validation";
import type { GeoPoint, SafetyIndexValue, ScenarioSummary, Trip } from "../domain/types";
import { hashString } from "./random";
import { createMockSafetyField, generateMockSafetyResponse, type MockSafetyField } from "./safetyField";
import { generateMockScenario } from "./tripGenerator";

/** Seed, data volume, latency and failure settings for mock clients. */
export interface MockClientOptions {
  tripCount: number;
  seed: number;
  latencyMs: number;
  /** Simulate a failure to exercise the UI's error states. */
  fail: boolean;
}

interface MockScenarioDefinition {
  id: string;
  name: string;
  description: string;
  origin: GeoPoint;
}

/** Mock scenarios with fixed origins and synthetic trips unrelated to the real network. */
export const MOCK_SCENARIOS: readonly MockScenarioDefinition[] = [
  {
    id: "mock-chatelet",
    name: "Châtelet (simulé)",
    description: "Scénario simulé : trajets synthétiques au départ de Châtelet - Les Halles.",
    origin: { latitude: 48.8619, longitude: 2.3466 },
  },
  {
    id: "mock-bercy",
    name: "Bercy (simulé)",
    description: "Scénario simulé : trajets synthétiques au départ de Bercy.",
    origin: { latitude: 48.8388, longitude: 2.3786 },
  },
  {
    id: "mock-saint-denis",
    name: "Saint-Denis (simulé)",
    description: "Scénario simulé : trajets synthétiques au départ de Saint-Denis.",
    origin: { latitude: 48.9362, longitude: 2.3574 },
  },
];

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(signal.reason);
      },
      { once: true },
    );
  });
}

/**
 * Simulate the routing API and pass JSON responses through the HTTP client's
 * validators so consumers receive the same domain types.
 */
export class MockScenariosClient implements ScenariosClient {
  constructor(private readonly options: MockClientOptions) {}

  private generate(definition: MockScenarioDefinition) {
    const seed = (this.options.seed ^ hashString(definition.id)) >>> 0;
    return generateMockScenario({ ...definition, tripCount: this.options.tripCount, seed });
  }

  async listScenarios(signal?: AbortSignal): Promise<ScenarioSummary[]> {
    await delay(this.options.latencyMs / 2, signal);
    if (this.options.fail) {
      throw new Error("Simulated failure of the routing service");
    }
    const summaries = MOCK_SCENARIOS.map((definition) => {
      const { journeys: _journeys, ...summary } = this.generate(definition);
      return summary;
    });
    return parseScenarioListResponse(JSON.parse(JSON.stringify(summaries)));
  }

  async fetchScenarioTrips(scenarioId: string, signal?: AbortSignal): Promise<Trip[]> {
    await delay(this.options.latencyMs, signal);
    if (this.options.fail) {
      throw new Error("Simulated failure of the routing service");
    }
    const definition = MOCK_SCENARIOS.find((scenario) => scenario.id === scenarioId);
    if (!definition) {
      throw new Error(`Routing service responded with HTTP 404 (unknown scenario "${scenarioId}")`);
    }
    return parseScenarioResponse(JSON.parse(JSON.stringify(this.generate(definition))), scenarioId);
  }
}

/** Simulate the safety API using a seeded synthetic field. */
export class MockSafetyIndexClient implements SafetyIndexClient {
  private readonly field: MockSafetyField;

  constructor(private readonly options: MockClientOptions) {
    this.field = createMockSafetyField(options.seed);
  }

  async fetchSafetyIndices(points: GeoPoint[], signal?: AbortSignal): Promise<SafetyIndexValue[]> {
    await delay(this.options.latencyMs / 2, signal);
    if (this.options.fail) {
      throw new Error("Simulated failure of the safety index service");
    }
    return parseSafetyIndexResponse(generateMockSafetyResponse(this.field, points), points.length);
  }

  async fetchJourneySafety(trips: Trip[], weights: SafetyWeights, signal?: AbortSignal): Promise<JourneySafetyResultDto[]> {
    const values = await this.fetchSafetyIndices(
      trips.flatMap((trip) => trip.path.map(([longitude, latitude]) => ({ longitude, latitude }))),
      signal,
    );
    let cursor = 0;
    return trips.map((trip) => {
      const local = values.slice(cursor, cursor + trip.path.length);
      cursor += trip.path.length;
      // Synthetic components exercise the controls without pretending to model real transit.
      return {
        journey_id: trip.id, values: local,
        score: 0.3 * weights.lighting + 0.7 * weights.ridership + 0.5 * weights.population_density,
      };
    });
  }
}
