import { describe, expect, it } from "vitest";
import { parseTripsResponse } from "../api/validation";
import { createMockSafetyField, generateMockSafetyResponse } from "./safetyField";
import { generateMockTripsResponse, ILE_DE_FRANCE_BOUNDS } from "./tripGenerator";
import { MockSafetyIndexClient, MockTripsClient } from "./mockClients";

const origin = { latitude: 48.8619, longitude: 2.3466 };

describe("generateMockTripsResponse", () => {
  it("generates the requested number of valid trips inside Ile-de-France", () => {
    const response = generateMockTripsResponse({ origin, tripCount: 50, seed: 1 });
    const trips = parseTripsResponse(response);
    expect(trips).toHaveLength(50);
    for (const trip of trips) {
      expect(trip.path.length).toBeGreaterThanOrEqual(10);
      expect(trip.timestampsMs).toEqual([...trip.timestampsMs].sort((a, b) => a - b));
      expect(trip.endTimeMs).toBeGreaterThan(trip.startTimeMs);
      for (const [longitude, latitude] of trip.path) {
        expect(longitude).toBeGreaterThanOrEqual(ILE_DE_FRANCE_BOUNDS.minLongitude);
        expect(longitude).toBeLessThanOrEqual(ILE_DE_FRANCE_BOUNDS.maxLongitude);
        expect(latitude).toBeGreaterThanOrEqual(ILE_DE_FRANCE_BOUNDS.minLatitude);
        expect(latitude).toBeLessThanOrEqual(ILE_DE_FRANCE_BOUNDS.maxLatitude);
      }
    }
  });

  it("produces varied durations and is deterministic for a given seed", () => {
    const first = parseTripsResponse(generateMockTripsResponse({ origin, tripCount: 30, seed: 7 }));
    const second = parseTripsResponse(generateMockTripsResponse({ origin, tripCount: 30, seed: 7 }));
    expect(second).toEqual(first);
    const durations = new Set(first.map((trip) => Math.round((trip.endTimeMs - trip.startTimeMs) / 60000)));
    expect(durations.size).toBeGreaterThan(10);
  });

  it("starts the default simulation on November 10 at 22:00 Paris time", () => {
    const trips = parseTripsResponse(generateMockTripsResponse({ origin, tripCount: 30, seed: 7 }));
    const start = Date.parse("2026-11-10T22:00:00+01:00");
    for (const trip of trips) {
      expect(trip.startTimeMs).toBeGreaterThanOrEqual(start);
      expect(trip.startTimeMs).toBeLessThan(start + 90 * 60_000);
    }
  });

  it("supports an empty result and large volumes", () => {
    expect(generateMockTripsResponse({ origin, tripCount: 0, seed: 1 }).trips).toEqual([]);
    expect(generateMockTripsResponse({ origin, tripCount: 3000, seed: 1 }).trips).toHaveLength(3000);
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

  it("return domain objects through the same contract as the API", async () => {
    const trips = await new MockTripsClient(options).fetchTrips(origin);
    expect(trips).toHaveLength(5);
    const points = trips.flatMap((trip) => trip.path.map(([longitude, latitude]) => ({ latitude, longitude })));
    const indices = await new MockSafetyIndexClient(options).fetchSafetyIndices(points);
    expect(indices).toHaveLength(points.length);
  });

  it("can simulate service failures", async () => {
    await expect(new MockTripsClient({ ...options, fail: true }).fetchTrips(origin)).rejects.toThrow();
    await expect(
      new MockSafetyIndexClient({ ...options, fail: true }).fetchSafetyIndices([origin]),
    ).rejects.toThrow();
  });

  it("honours abort signals", async () => {
    const controller = new AbortController();
    const promise = new MockTripsClient({ ...options, latencyMs: 1000 }).fetchTrips(origin, controller.signal);
    controller.abort();
    await expect(promise).rejects.toBeDefined();
  });
});
