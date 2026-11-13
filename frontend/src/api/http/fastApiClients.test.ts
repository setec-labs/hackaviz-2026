import { afterEach, describe, expect, it, vi } from "vitest";
import type { Trip } from "../../domain/types";
import { parseJourneySafetyResponse } from "../validation";
import { FastApiSafetyIndexClient } from "./fastApiClients";

const start = Date.parse("2026-11-08T00:10:00+01:00");
const trip: Trip = {
  id: "journey-1", destinationName: "Destination", destinationPopulation: null,
  mode: "transit", pointModes: ["walk_access", "transit"],
  startTimeMs: start, endTimeMs: start + 120_000,
  timestampsMs: [start, start + 60_000],
  path: [[2.3, 48.8], [2.4, 48.9]],
  legs: [
    {
      mode: "walk_access", startTimeMs: start, endTimeMs: start + 60_000,
      fromStop: "ORIGIN", toStop: "A", gtfsTripId: null, pointRange: [0, 1],
    },
    {
      mode: "transit", startTimeMs: start + 60_000, endTimeMs: start + 120_000,
      fromStop: "A", toStop: "B", gtfsTripId: "T", pointRange: [1, 2],
    },
  ],
};

const weights = { lighting: 0.25, ridership: 0.5, population_density: 0.25 };
const result = { journey_id: trip.id, values: [0.2, 0.8], score: 0.65 };

afterEach(() => vi.unstubAllGlobals());

describe("contextual safety HTTP client", () => {
  it("sends arc identity, times, points and normalized weights", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ journeys: [result] })));
    vi.stubGlobal("fetch", fetch);
    const signal = new AbortController().signal;
    const values = await new FastApiSafetyIndexClient("http://localhost:8002").fetchJourneySafety([trip], weights, signal);
    expect(values).toEqual([result]);
    const [url, options] = fetch.mock.calls[0]!;
    expect(url.pathname).toBe("/journey-safety");
    expect(options.signal).toBe(signal);
    const body = JSON.parse(options.body);
    expect(body.weights).toEqual(weights);
    expect(body.journeys[0].coordinates).toEqual(trip.path);
    expect(body.journeys[0].offsets_s).toEqual([0, 60]);
    expect(body.journeys[0].legs[1]).toMatchObject({
      from_stop: "A", to_stop: "B", gtfs_trip_id: "T",
      start_time: "2026-11-07T23:11:00.000Z",
      end_time: "2026-11-07T23:12:00.000Z",
    });
  });

  it("batches without splitting journeys and preserves order", async () => {
    const trips = Array.from({ length: 101 }, (_, index) => ({ ...trip, id: `j${index}` }));
    const fetch = vi.fn().mockImplementation((_url, options) => {
      const { journeys } = JSON.parse(options.body);
      return Promise.resolve(new Response(JSON.stringify({
        journeys: journeys.map((journey: { journey_id: string }) => ({ ...result, journey_id: journey.journey_id })),
      })));
    });
    vi.stubGlobal("fetch", fetch);
    const results = await new FastApiSafetyIndexClient("http://localhost:8002").fetchJourneySafety(trips, weights);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(results.map((item) => item.journey_id)).toEqual(trips.map((item) => item.id));
  });

  it("respects the coordinate limit and surfaces HTTP and context failures", async () => {
    const fetch = vi.fn().mockImplementation((_url, options) => {
      const { journeys } = JSON.parse(options.body);
      return Promise.resolve(new Response(JSON.stringify({
        journeys: journeys.map((journey: { journey_id: string; coordinates: unknown[] }) => ({
          journey_id: journey.journey_id, values: journey.coordinates.map(() => null), score: null,
        })),
      })));
    });
    vi.stubGlobal("fetch", fetch);
    const client = new FastApiSafetyIndexClient("http://localhost:8002");
    const large = { ...trip, path: Array.from({ length: 3000 }, () => trip.path[0]!) };
    const results = await client.fetchJourneySafety([large, { ...large, id: "other" }], weights);
    expect(results.map((item) => item.values.length)).toEqual([3000, 3000]);
    expect(fetch).toHaveBeenCalledTimes(2);
    await expect(client.fetchJourneySafety([{ ...large, path: Array(5001).fill(trip.path[0]) }], weights)).rejects.toThrow("5,000");
    await expect(client.fetchJourneySafety([{ ...trip, legs: undefined }], weights)).rejects.toThrow("routing context");
    fetch.mockResolvedValue(new Response("unavailable", { status: 503 }));
    await expect(client.fetchJourneySafety([trip], weights)).rejects.toThrow("HTTP 503");
  });
});

describe("journey safety response validation", () => {
  it("preserves unavailable data without manufacturing a score", () => {
    expect(parseJourneySafetyResponse({ journeys: [{ ...result, values: [0.2, null], score: null }] }, [trip]))
      .toEqual([{ ...result, values: [0.2, null], score: null }]);
  });

  it.each([
    {}, { journeys: [] },
    { journeys: [{ ...result, journey_id: "other" }] },
    { journeys: [{ ...result, values: [0.2] }] },
    { journeys: [{ ...result, values: [0.2, 2] }] },
    { journeys: [{ ...result, score: undefined }] },
    { journeys: [{ ...result, score: Number.NaN }] },
  ])("rejects malformed or misaligned results", (response) => {
    expect(() => parseJourneySafetyResponse(response, [trip])).toThrow();
  });
});
