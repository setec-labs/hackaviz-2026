import type { GeoPoint, SafetyIndexValue, ScenarioSummary, Trip } from "../../domain/types";
import type { SafetyIndexClient, ScenariosClient } from "../clients";
import type { JourneyDto, JourneySafetyRequestDto, JourneySafetyResultDto, SafetyIndexRequestDto, SafetyWeights } from "../contracts";
import { ContractError, parseJourneySafetyResponse, parseSafetyIndexResponse, parseScenarioListResponse, parseScenarioResponse } from "../validation";

const SAFETY_BATCH_SIZE = 5000;

function toJourneyDto(trip: Trip): JourneyDto {
  if (!trip.legs?.length) throw new ContractError(`Journey ${trip.id}: missing routing context`);
  const destination = trip.path[trip.path.length - 1];
  if (!destination) throw new ContractError(`Journey ${trip.id}: missing coordinates`);
  return {
    journey_id: trip.id,
    destination: {
      name: trip.destinationName ?? trip.id,
      longitude: destination[0],
      latitude: destination[1],
      population: trip.destinationPopulation,
    },
    start_time: new Date(trip.startTimeMs).toISOString(),
    end_time: new Date(trip.endTimeMs).toISOString(),
    coordinates: trip.path,
    offsets_s: trip.timestampsMs.map((timestamp) => (timestamp - trip.startTimeMs) / 1000),
    legs: trip.legs.map((leg) => ({
      mode: leg.mode,
      start_time: new Date(leg.startTimeMs).toISOString(),
      end_time: new Date(leg.endTimeMs).toISOString(),
      from_stop: leg.fromStop,
      to_stop: leg.toStop,
      gtfs_trip_id: leg.gtfsTripId,
      point_range: leg.pointRange,
    })),
  };
}

async function readJson(response: Response, service: string): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`${service} service responded with HTTP ${response.status}`);
  }
  return response.json();
}

/** Loads and validates scenario data from the routing API. */
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

/** Loads safety indices in batches respecting the API's 5,000-position limit. */
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

  async fetchJourneySafety(trips: Trip[], weights: SafetyWeights, signal?: AbortSignal): Promise<JourneySafetyResultDto[]> {
    const results: JourneySafetyResultDto[] = [];
    let offset = 0;
    while (offset < trips.length) {
      const batch: Trip[] = [];
      let points = 0;
      while (offset < trips.length && batch.length < 100) {
        const trip = trips[offset]!;
        if (trip.path.length > SAFETY_BATCH_SIZE) {
          throw new ContractError(`Journey ${trip.id} exceeds the 5,000-coordinate safety limit`);
        }
        if (points + trip.path.length > SAFETY_BATCH_SIZE) break;
        points += trip.path.length;
        batch.push(trip);
        offset += 1;
      }
      const body: JourneySafetyRequestDto = { journeys: batch.map(toJourneyDto), weights };
      const response = await fetch(new URL("/journey-safety", this.baseUrl), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });
      results.push(...parseJourneySafetyResponse(await readJson(response, "Safety"), batch));
    }
    return results;
  }
}
