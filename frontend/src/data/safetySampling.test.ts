import { describe, expect, it } from "vitest";
import type { Trip } from "../domain/types";
import { isImplausible, mergeJourneySafety } from "./safetySampling";

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
  it("aligns contextual local values and global scores without replacing missing data", () => {
    const merged = mergeJourneySafety(trips, [
      { journey_id: "b", values: [0.8, 0.8], score: 0.8 },
      { journey_id: "a", values: [0.9, null, 0.6, 0.6, 0.1], score: null },
    ]);
    expect(merged.values).toEqual([0.9, null, 0.6, 0.6, 0.1, 0.8, 0.8]);
    expect(merged.scores.get("a")).toBeNull();
    expect(merged.scores.get("b")).toBe(0.8);
  });

  it("skips trips longer than 2 hours", () => {
    const long: Trip = { ...trips[0]!, id: "long", timestampsMs: [0, 1000, 2000, 3000, 7_201_000] };
    expect(isImplausible(long)).toBe(true);
    expect(mergeJourneySafety([long], []).values).toEqual([null, null, null, null, null]);
    const boundary = { ...long, timestampsMs: [0, 1000, 2000, 3000, 7_200_000] };
    expect(isImplausible(boundary)).toBe(false);
  });

  it("keeps all modes unavailable after a safety service failure, without a 0.5 placeholder", () => {
    const merged = mergeJourneySafety(trips, []);
    expect(merged.values).toEqual([null, null, null, null, null, null, null]);
    expect([...merged.scores.values()]).toEqual([null, null]);
  });
});
