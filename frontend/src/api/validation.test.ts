import { describe, expect, it } from "vitest";
import {
  ContractError,
  parseSafetyIndexResponse,
  parseScenarioListResponse,
  parseScenarioResponse,
  summarizeJourneyMode,
} from "./validation";

const summary = {
  id: "CHU-Avicenne",
  name: "CHU Avicenne",
  description: "Départ le 08/11/2026 à 00:05 : 1 trajets vers 1 destinations.",
  metadata_generated: true,
  origin: { latitude: 48.916, longitude: 2.425 },
  departure_time: "2026-11-08T00:05:00+01:00",
  journey_count: 1,
};

const journey = {
  journey_id: "j-1",
  destination: { latitude: 48.87, longitude: 2.36, name: "Paris 10e", population: null },
  start_time: "2026-11-08T00:05:00+01:00",
  end_time: "2026-11-08T00:15:00+01:00",
  legs: [
    {
      mode: "walk_access",
      start_time: "2026-11-08T00:05:00+01:00",
      end_time: "2026-11-08T00:08:00+01:00",
      from_stop: "ORIGIN",
      to_stop: "S1",
      gtfs_trip_id: null,
      point_range: [0, 2],
    },
    {
      mode: "transit",
      start_time: "2026-11-08T00:08:00+01:00",
      end_time: "2026-11-08T00:15:00+01:00",
      from_stop: "S1",
      to_stop: "DESTINATION",
      gtfs_trip_id: "T1",
      point_range: [2, 3],
    },
  ],
  coordinates: [
    [2.425, 48.916],
    [2.41, 48.9],
    [2.36, 48.87],
  ],
  offsets_s: [0, 180, 600],
};

const scenario = { ...summary, journeys: [journey] };
const start = Date.parse(journey.start_time);

describe("parseScenarioListResponse", () => {
  it("maps summaries to domain objects", () => {
    expect(parseScenarioListResponse([summary])).toEqual([
      {
        id: "CHU-Avicenne",
        name: "CHU Avicenne",
        description: summary.description,
        metadataGenerated: true,
        origin: summary.origin,
        departureTimeMs: Date.parse(summary.departure_time),
        journeyCount: 1,
      },
    ]);
    expect(parseScenarioListResponse([])).toEqual([]);
  });

  it.each([
    ["not an array", {}],
    ["missing name", [{ ...summary, name: "" }]],
    ["missing metadata flag", [{ ...summary, metadata_generated: undefined }]],
    ["invalid origin", [{ ...summary, origin: { latitude: 120, longitude: 2 } }]],
    ["invalid departure", [{ ...summary, departure_time: "tonight" }]],
    ["negative count", [{ ...summary, journey_count: -1 }]],
  ])("rejects %s", (_label, payload) => {
    expect(() => parseScenarioListResponse(payload)).toThrow(ContractError);
  });
});

describe("parseScenarioResponse", () => {
  it("converts journeys to timed trips", () => {
    expect(parseScenarioResponse(scenario, "CHU-Avicenne")).toEqual([
      {
        id: "j-1",
        destinationName: "Paris 10e",
        destinationPopulation: null,
        mode: "transit",
        pointModes: ["walk_access", "walk_access", "transit"],
        startTimeMs: start,
        endTimeMs: Date.parse(journey.end_time),
        path: journey.coordinates,
        timestampsMs: [start, start + 180_000, start + 600_000],
      },
    ]);
  });

  it("reads the destination population when provided", () => {
    const withPopulation = { ...journey, destination: { ...journey.destination, population: 12_345 } };
    const [trip] = parseScenarioResponse({ ...scenario, journeys: [withPopulation] }, "CHU-Avicenne");
    expect(trip?.destinationPopulation).toBe(12_345);
  });

  const legs = journey.legs;
  it.each([
    ["another scenario", { ...scenario, id: "Metropolis" }],
    ["negative population", { ...scenario, journeys: [{ ...journey, destination: { ...journey.destination, population: -1 } }] }],
    ["gap between legs", { ...scenario, journeys: [{ ...journey, legs: [legs[0], { ...legs[1], point_range: [1, 3] }] }] }],
    ["uncovered points", { ...scenario, journeys: [{ ...journey, legs: [{ ...legs[0], point_range: [0, 2] }] }] }],
    ["count mismatch", { ...scenario, journey_count: 2 }],
    ["no legs", { ...scenario, journeys: [{ ...journey, legs: [] }] }],
    ["single point", { ...scenario, journeys: [{ ...journey, coordinates: [[2.4, 48.9]], offsets_s: [0] }] }],
    ["offset count", { ...scenario, journeys: [{ ...journey, offsets_s: [0, 180] }] }],
    ["decreasing offsets", { ...scenario, journeys: [{ ...journey, offsets_s: [0, 600, 180] }] }],
    ["invalid coordinate", { ...scenario, journeys: [{ ...journey, coordinates: [[2.4, 95], [2.4, 48.9], [2.3, 48.8]] }] }],
    ["end before start", { ...scenario, journeys: [{ ...journey, end_time: "2026-11-08T00:00:00+01:00" }] }],
  ])("rejects %s", (_label, payload) => {
    expect(() => parseScenarioResponse(payload, "CHU-Avicenne")).toThrow(ContractError);
  });
});

describe("summarizeJourneyMode", () => {
  it("summarizes multimodal legs without inventing a mode", () => {
    expect(summarizeJourneyMode(["walk_access", "wait", "transit", "walk_egress"])).toBe("transit");
    expect(summarizeJourneyMode(["walk_direct"])).toBe("walk");
    expect(summarizeJourneyMode(["bike"])).toBe("bike");
    expect(summarizeJourneyMode(["wait"])).toBeNull();
  });
});

describe("parseSafetyIndexResponse", () => {
  it("accepts values in [0, 1] and null", () => {
    const response = {
      indices: [
        { latitude: 48.8, longitude: 2.3, value: 0.4 },
        { latitude: 48.8, longitude: 2.3, value: null },
      ],
    };
    expect(parseSafetyIndexResponse(response, 2)).toEqual([0.4, null]);
  });

  it("rejects out-of-range values and length mismatches", () => {
    expect(() => parseSafetyIndexResponse({ indices: [{ value: 1.5 }] }, 1)).toThrow(ContractError);
    expect(() => parseSafetyIndexResponse({ indices: [{ value: "high" }] }, 1)).toThrow(ContractError);
    expect(() => parseSafetyIndexResponse({ indices: [] }, 1)).toThrow(ContractError);
    expect(() => parseSafetyIndexResponse({}, 0)).toThrow(ContractError);
  });
});
