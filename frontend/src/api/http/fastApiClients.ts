import type { GeoPoint, SafetyIndexValue, Trip } from "../../domain/types";
import type { SafetyIndexClient, TripsClient } from "../clients";
import type { SafetyIndexRequestDto } from "../contracts";
import { parseSafetyIndexResponse, parseTripsResponse } from "../validation";

/*
 * Clients des API FastAPI. `POST /safety-index` est servi par `services/safety`.
 * `GET /trips` est PROVISOIRE : a aligner sur `services/routing` lorsqu'il l'exposera.
 */

const SAFETY_BATCH_SIZE = 5000;

async function readJson(response: Response, service: string): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`${service} service responded with HTTP ${response.status}`);
  }
  return response.json();
}

export class FastApiTripsClient implements TripsClient {
  constructor(private readonly baseUrl: string) {}

  async fetchTrips(origin: GeoPoint, signal?: AbortSignal): Promise<Trip[]> {
    const url = new URL("/trips", this.baseUrl);
    url.searchParams.set("latitude", String(origin.latitude));
    url.searchParams.set("longitude", String(origin.longitude));
    const response = await fetch(url, { signal });
    return parseTripsResponse(await readJson(response, "Trips"));
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
