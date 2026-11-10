import { describe, expect, it } from "vitest";
import { ContractError, parseSafetyIndexResponse, parseTripsResponse } from "./validation";

const validTrip = {
  trip_id: "t1",
  start_time: "2026-11-10T22:00:00+01:00",
  end_time: "2026-11-10T22:10:00+01:00",
  mode: "walk",
  points: [
    { latitude: 48.86, longitude: 2.35, timestamp: "2026-11-10T22:00:00+01:00" },
    { latitude: 48.87, longitude: 2.36, timestamp: "2026-11-10T22:10:00+01:00" },
  ],
};

describe("parseTripsResponse", () => {
  it("maps a valid response to domain trips", () => {
    const [trip] = parseTripsResponse({ origin: { latitude: 48.86, longitude: 2.35 }, trips: [validTrip] });
    expect(trip).toEqual({
      id: "t1",
      mode: "walk",
      startTimeMs: Date.parse(validTrip.start_time),
      endTimeMs: Date.parse(validTrip.end_time),
      path: [
        [2.35, 48.86],
        [2.36, 48.87],
      ],
      timestampsMs: [Date.parse(validTrip.start_time), Date.parse(validTrip.end_time)],
    });
  });

  it("keeps a missing mode as null instead of inventing one", () => {
    const { mode: _mode, ...withoutMode } = validTrip;
    expect(parseTripsResponse({ trips: [withoutMode] })[0]?.mode).toBeNull();
  });

  it.each([
    ["not an object", null],
    ["missing trips", {}],
    ["missing id", { trips: [{ ...validTrip, trip_id: "" }] }],
    ["single point", { trips: [{ ...validTrip, points: validTrip.points.slice(0, 1) }] }],
    ["invalid timestamp", { trips: [{ ...validTrip, start_time: "tonight" }] }],
    ["end before start", { trips: [{ ...validTrip, end_time: "2026-11-10T21:00:00+01:00" }] }],
    [
      "invalid latitude",
      { trips: [{ ...validTrip, points: [{ ...validTrip.points[0], latitude: 120 }, validTrip.points[1]] }] },
    ],
    ["unordered points", { trips: [{ ...validTrip, points: [...validTrip.points].reverse() }] }],
  ])("rejects %s", (_label, payload) => {
    expect(() => parseTripsResponse(payload)).toThrow(ContractError);
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
