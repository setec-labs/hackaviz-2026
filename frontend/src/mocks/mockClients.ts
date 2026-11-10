import type { SafetyIndexClient, TripsClient } from "../api/clients";
import { parseSafetyIndexResponse, parseTripsResponse } from "../api/validation";
import type { GeoPoint, SafetyIndexValue, Trip } from "../domain/types";
import { hashString } from "./random";
import { createMockSafetyField, generateMockSafetyResponse, type MockSafetyField } from "./safetyField";
import { generateMockTripsResponse } from "./tripGenerator";

export interface MockClientOptions {
  tripCount: number;
  seed: number;
  latencyMs: number;
  /** Simule une panne pour verifier les etats d'erreur de l'interface. */
  fail: boolean;
}

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
 * Simule l'API trajets. La reponse passe par JSON puis par le meme validateur que le
 * client HTTP, afin que le reste de l'application ne fasse aucune difference.
 */
export class MockTripsClient implements TripsClient {
  constructor(private readonly options: MockClientOptions) {}

  async fetchTrips(origin: GeoPoint, signal?: AbortSignal): Promise<Trip[]> {
    await delay(this.options.latencyMs, signal);
    if (this.options.fail) {
      throw new Error("Simulated failure of the trips service");
    }
    const seed = (this.options.seed ^ hashString(`${origin.latitude.toFixed(4)},${origin.longitude.toFixed(4)}`)) >>> 0;
    const response = generateMockTripsResponse({ origin, tripCount: this.options.tripCount, seed });
    return parseTripsResponse(JSON.parse(JSON.stringify(response)));
  }
}

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
}
