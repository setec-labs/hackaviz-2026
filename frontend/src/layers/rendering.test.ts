import { describe, expect, it } from "vitest";
import { prepareDataset, countActiveTrips } from "../data/prepareDataset";
import { classifySafetyIndex, safetyIndexColor } from "../domain/safetyLevels";
import type { Trip } from "../domain/types";
import { rgba } from "../theme/palette";
import { findSegment, HeadBuffers } from "./headPositions";

const base = Date.parse("2026-11-10T22:00:00Z");
const trips: Trip[] = [
  {
    id: "a",
    destinationName: "Destination A",
    destinationPopulation: 12_000,
    mode: "walk",
    pointModes: ["walk_access", "transit", "transit"],
    startTimeMs: base,
    endTimeMs: base + 200_000,
    path: [
      [2.3, 48.8],
      [2.4, 48.8],
      [2.4, 48.9],
    ],
    timestampsMs: [base, base + 100_000, base + 200_000],
  },
  {
    id: "b",
    destinationName: null,
    destinationPopulation: null,
    mode: null,
    pointModes: ["wait", "walk_egress"],
    startTimeMs: base + 150_000,
    endTimeMs: base + 300_000,
    path: [
      [2.0, 48.0],
      [2.1, 48.1],
    ],
    timestampsMs: [base + 150_000, base + 300_000],
  },
];

describe("safety levels", () => {
  it("classifies values and keeps missing values explicit", () => {
    expect(classifySafetyIndex(0.9).id).toBe("favorable");
    expect(classifySafetyIndex(0.5).id).toBe("intermediate");
    expect(classifySafetyIndex(0.3).id).toBe("vigilance");
    expect(classifySafetyIndex(0.1).id).toBe("high-vigilance");
    expect(classifySafetyIndex(null).id).toBe("unavailable");
  });

  it("uses the palette at the ends of the scale", () => {
    expect(safetyIndexColor(1)).toEqual(rgba("trip"));
    expect(safetyIndexColor(0)).toEqual(rgba("vigilanceHigh"));
    expect(safetyIndexColor(0.3)).toEqual(rgba("vigilance"));
    expect(safetyIndexColor(null)).toEqual(rgba("textMuted"));
  });
});

describe("prepareDataset", () => {
  it("converts times to seconds relative to the earliest start and spreads indices per vertex", () => {
    const dataset = prepareDataset(trips, [1, 0.3, null, 0, 0.5]);
    expect(dataset.endTime).toBe(300);
    expect(dataset.trips[0]?.timestamps).toEqual([0, 100, 200]);
    expect(dataset.trips[0]?.safety).toEqual([1, 0.3, null]);
    expect(dataset.trips[1]?.safety).toEqual([0, 0.5]);
    expect(countActiveTrips(dataset, 175)).toBe(2);
    expect(countActiveTrips(dataset, 250)).toBe(1);
  });

  it("marks every index as unavailable when the safety service failed", () => {
    const dataset = prepareDataset(trips, null);
    expect(dataset.trips.flatMap((trip) => trip.safety).every((value) => value === null)).toBe(true);
  });

  it("handles an empty trip list", () => {
    expect(prepareDataset([], null)).toEqual({
      trips: [],
      arrivals: [],
      constellation: [],
      originMs: 0,
      startTime: 0,
      endTime: 0,
    });
  });

  it("builds arrival bubbles sorted by arrival time", () => {
    const dataset = prepareDataset(trips, [1, 0.3, null, 0, 0.5]);
    expect(dataset.arrivals.map((arrival) => [arrival.id, arrival.time, arrival.position])).toEqual([
      ["a", 200, [2.4, 48.9]],
      ["b", 300, [2.1, 48.1]],
    ]);
    expect(dataset.arrivals[0]).toMatchObject({ population: 12_000, populationSimulated: false, implausible: false });
    expect(dataset.arrivals[0]?.worstWindowSafety).toBeCloseTo(0.475);
    expect(dataset.arrivals[1]?.populationSimulated).toBe(true);
    expect(dataset.arrivals[1]?.worstWindowSafety).toBeCloseTo(0.25);
    expect(dataset.constellation).toEqual([{ from: [2.4, 48.9], to: [2.1, 48.1], time: 300 }]);
  });

  it("shows trips longer than 2 hours in a neutral colour without an index", () => {
    const long: Trip = { ...trips[0]!, id: "long", endTimeMs: base + 3 * 3600_000, timestampsMs: [base, base + 3600_000, base + 3 * 3600_000] };
    const dataset = prepareDataset([long], [0.9, 0.9, 0.9]);
    expect(dataset.trips[0]?.implausible).toBe(true);
    expect(dataset.trips[0]?.colors.every((color) => color.slice(0, 3).join() === rgba("neutral").slice(0, 3).join())).toBe(true);
    expect(dataset.arrivals[0]).toMatchObject({ implausible: true, worstWindowSafety: null, color: rgba("neutral") });
  });
});

describe("head positions", () => {
  it("finds the segment containing a time", () => {
    expect(findSegment([0, 100, 200], 0)).toBe(0);
    expect(findSegment([0, 100, 200], 150)).toBe(1);
    expect(findSegment([0, 100, 200], 200)).toBe(1);
  });

  it("interpolates the current position of active trips only", () => {
    const dataset = prepareDataset(trips, [1, 0.3, null, 0, 0.5]);
    const heads = new HeadBuffers(dataset.trips.length);
    expect(heads.update(dataset, 50)).toBe(1);
    expect(heads.positions[0]).toBeCloseTo(2.35);
    expect(heads.positions[1]).toBeCloseTo(48.8);
    expect(heads.update(dataset, 175)).toBe(2);
    expect(heads.tripIndices[1]).toBe(1);
    expect(heads.update(dataset, 400)).toBe(0);
  });
});
