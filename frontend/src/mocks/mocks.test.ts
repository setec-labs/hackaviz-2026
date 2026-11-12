import { describe, expect, it } from "vitest";
import { parseScenarioResponse } from "../api/validation";
import { createMockSafetyField, generateMockSafetyResponse } from "./safetyField";
import { generateMockScenario, ILE_DE_FRANCE_BOUNDS } from "./tripGenerator";
import { MOCK_SCENARIOS, MockSafetyIndexClient, MockScenariosClient } from "./mockClients";

const origin = { latitude: 48.8619, longitude: 2.3466 };
const base = { id: "mock-test", name: "Test (simulé)", description: "Scénario simulé de test.", origin };

function generateTrips(tripCount: number, seed: number) {
  return parseScenarioResponse(generateMockScenario({ ...base, tripCount, seed }), base.id);
}

describe("generateMockScenario", () => {
  it("generates the requested number of valid trips from the scenario origin inside Ile-de-France", () => {
    const trips = generateTrips(50, 1);
    expect(trips).toHaveLength(50);
    for (const trip of trips) {
      expect(trip.path.length).toBeGreaterThanOrEqual(10);
      expect(trip.path[0]).toEqual([origin.longitude, origin.latitude]);
      expect(trip.timestampsMs).toEqual([...trip.timestampsMs].sort((a, b) => a - b));
      expect(trip.endTimeMs).toBeGreaterThan(trip.startTimeMs);
      expect(trip.destinationName).toMatch(/simulée/);
      for (const [longitude, latitude] of trip.path) {
        expect(longitude).toBeGreaterThanOrEqual(ILE_DE_FRANCE_BOUNDS.minLongitude);
        expect(longitude).toBeLessThanOrEqual(ILE_DE_FRANCE_BOUNDS.maxLongitude);
        expect(latitude).toBeGreaterThanOrEqual(ILE_DE_FRANCE_BOUNDS.minLatitude);
        expect(latitude).toBeLessThanOrEqual(ILE_DE_FRANCE_BOUNDS.maxLatitude);
      }
    }
  });

  it("produces varied durations and is deterministic for a given seed", () => {
    const first = generateTrips(30, 7);
    expect(generateTrips(30, 7)).toEqual(first);
    const durations = new Set(first.map((trip) => Math.round((trip.endTimeMs - trip.startTimeMs) / 60000)));
    expect(durations.size).toBeGreaterThan(10);
  });

  it("starts the default simulation on November 10 at 22:00 Paris time", () => {
    const start = Date.parse("2026-11-10T22:00:00+01:00");
    for (const trip of generateTrips(30, 7)) {
      expect(trip.startTimeMs).toBeGreaterThanOrEqual(start);
      expect(trip.startTimeMs).toBeLessThan(start + 90 * 60_000);
    }
  });

  it("supports an empty result and large volumes", () => {
    expect(generateMockScenario({ ...base, tripCount: 0, seed: 1 }).journeys).toEqual([]);
    expect(generateMockScenario({ ...base, tripCount: 3000, seed: 1 }).journeys).toHaveLength(3000);
  });
});

describe("mock safety field", () => {
  it("returns values in [0, 1] or null, in request order", () => {
    const field = createMockSafetyField(3);
    const points = Array.from({ length: 500 }, (_, i) => ({
      latitude: 48.5 + (i % 25) * 0.03,
      longitude: 1.9 + Math.floor(i / 25) * 0.05,
    }));
    const response = generateMockSafetyResponse(field, points);
    expect(response.indices).toHaveLength(points.length);
    response.indices.forEach((item, i) => {
      expect(item.latitude).toBe(points[i]?.latitude);
      if (item.value !== null) {
        expect(item.value).toBeGreaterThanOrEqual(0);
        expect(item.value).toBeLessThanOrEqual(1);
      }
    });
  });
});

describe("mock clients", () => {
  const options = { tripCount: 5, seed: 1, latencyMs: 0, fail: false };

  it("list the simulated scenarios and return their trips through the API contract", async () => {
    const client = new MockScenariosClient(options);
    const scenarios = await client.listScenarios();
    expect(scenarios.map((scenario) => scenario.id)).toEqual(MOCK_SCENARIOS.map((scenario) => scenario.id));
    expect(scenarios.every((scenario) => scenario.journeyCount === 5 && !scenario.metadataGenerated)).toBe(true);
    const firstScenario = scenarios[0];
    if (!firstScenario) throw new Error("Expected a mock scenario");
    const trips = await client.fetchScenarioTrips(firstScenario.id);
    expect(trips).toHaveLength(5);
    const points = trips.flatMap((trip) => trip.path.map(([longitude, latitude]) => ({ latitude, longitude })));
    const indices = await new MockSafetyIndexClient(options).fetchSafetyIndices(points);
    expect(indices).toHaveLength(points.length);
  });

  it("can simulate service failures and unknown scenarios", async () => {
    const failing = new MockScenariosClient({ ...options, fail: true });
    await expect(failing.listScenarios()).rejects.toThrow();
    await expect(failing.fetchScenarioTrips("mock-chatelet")).rejects.toThrow();
    await expect(new MockScenariosClient(options).fetchScenarioTrips("unknown")).rejects.toThrow();
    await expect(
      new MockSafetyIndexClient({ ...options, fail: true }).fetchSafetyIndices([origin]),
    ).rejects.toThrow();
  });

  it("honours abort signals", async () => {
    const controller = new AbortController();
    const promise = new MockScenariosClient({ ...options, latencyMs: 1000 }).fetchScenarioTrips(
      "mock-chatelet",
      controller.signal,
    );
    controller.abort();
    await expect(promise).rejects.toBeDefined();
  });
});
