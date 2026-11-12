import { describe, expect, it } from "vitest";
import type { Trip } from "../domain/types";
import {
  collectPedestrianPoints,
  isPedestrianMode,
  mergeSafetyValues,
  NON_PEDESTRIAN_SAFETY_VALUE,
} from "./safetySampling";

const trips: Trip[] = [
  {
    id: "a",
    destinationName: null,
    destinationPopulation: null,
    mode: "transit",
    pointModes: ["walk_access", "wait", "transit", "transit", "walk_egress"],
    startTimeMs: 0,
    endTimeMs: 4000,
    path: [
      [2.0, 48.0],
      [2.1, 48.1],
      [2.2, 48.2],
      [2.3, 48.3],
      [2.4, 48.4],
    ],
    timestampsMs: [0, 1000, 2000, 3000, 4000],
  },
  {
    id: "b",
    destinationName: null,
    destinationPopulation: null,
    mode: "bike",
    pointModes: ["bike", "bike"],
    startTimeMs: 0,
    endTimeMs: 1000,
    path: [
      [2.5, 48.5],
      [2.6, 48.6],
    ],
    timestampsMs: [0, 1000],
  },
];

describe("safety sampling", () => {
  it("only treats walking and waiting as pedestrian modes", () => {
    for (const mode of ["walk", "walk_access", "walk_egress", "walk_transfer", "walk_direct", "wait"]) {
      expect(isPedestrianMode(mode)).toBe(true);
    }
    for (const mode of ["transit", "bike", "night_bus", "car", ""]) {
      expect(isPedestrianMode(mode)).toBe(false);
    }
  });

  it("requests the safety index for walking and waiting points only", () => {
    expect(collectPedestrianPoints(trips)).toEqual([
      { longitude: 2.0, latitude: 48.0 },
      { longitude: 2.1, latitude: 48.1 },
      { longitude: 2.4, latitude: 48.4 },
    ]);
  });

  it("skips trips longer than 2 hours", () => {
    const long: Trip = { ...trips[0]!, id: "long", timestampsMs: [0, 1000, 2000, 3000, 7_201_000] };
    expect(collectPedestrianPoints([long])).toEqual([]);
    expect(mergeSafetyValues([long], [])).toEqual([null, null, null, null, null]);
  });

  it("uses the neutral placeholder elsewhere and keeps failures explicit", () => {
    const neutral = NON_PEDESTRIAN_SAFETY_VALUE;
    expect(neutral).toBe(0.5);
    expect(mergeSafetyValues(trips, [0.9, null, 0.1])).toEqual([0.9, null, neutral, neutral, 0.1, neutral, neutral]);
    expect(mergeSafetyValues(trips, null)).toEqual([null, null, neutral, neutral, null, neutral, neutral]);
  });
});
