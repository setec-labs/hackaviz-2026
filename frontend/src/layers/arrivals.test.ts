import { describe, expect, it, vi } from "vitest";
import {
  ANXIETY_WORST_SECONDS,
  buildArrivals,
  buildConstellation,
  countReached,
  populationRadiusPx,
  populationScale,
  simulatePopulation,
  worstMinutesSafety,
  type ArrivalSource,
} from "../data/arrivals";
import { safetyIndexColor } from "../domain/safetyLevels";
import { rgba } from "../theme/palette";
import { ArrivalTracker, FLASH_DURATION_MS } from "./arrivalTracker";

function source(id: string, endTime: number, position: [number, number], population: number | null = null): ArrivalSource {
  return {
    id,
    destinationName: null,
    destinationPopulation: population,
    path: [[2.35, 48.85], position],
    timestamps: [0, endTime],
    safety: [0.8, 0.6],
    endTime,
  };
}

describe("worstMinutesSafety", () => {
  it("finds the worst 10 minutes anywhere along the trip", () => {
    expect(ANXIETY_WORST_SECONDS).toBe(600);
    // The worst window is in the middle: favorable, unfavorable, then favorable.
    const timestamps = [0, 1800, 1800, 2400, 2400, 3600];
    expect(worstMinutesSafety(timestamps, [0.9, 0.9, 0.1, 0.1, 0.9, 0.9])).toBeCloseTo(0.1);
    // The worst passage at the start counts as much as one at the end.
    expect(worstMinutesSafety([0, 600, 600, 3600], [0.2, 0.2, 0.8, 0.8])).toBeCloseTo(0.2);
  });

  it("adds up the worst minutes even when they are not consecutive", () => {
    // Two 5-minute passages at 0.2, separated by 30 minutes at 0.8, average 0.2.
    const timestamps = [0, 300, 300, 2100, 2100, 2400, 2400, 3600];
    expect(worstMinutesSafety(timestamps, [0.2, 0.2, 0.8, 0.8, 0.2, 0.2, 0.8, 0.8])).toBeCloseTo(0.2);
  });

  it("averages over 10 minutes rather than keeping a single low point", () => {
    // Five minutes at 0.2 surrounded by 0.8 give a worst-ten-minute mean of 0.5.
    const timestamps = [0, 1200, 1200, 1500, 1500, 2700];
    expect(worstMinutesSafety(timestamps, [0.8, 0.8, 0.2, 0.2, 0.8, 0.8])).toBeCloseTo(0.5);
  });

  it("uses the whole trip when shorter than the window and ignores missing values", () => {
    expect(worstMinutesSafety([0, 300], [0.4, null])).toBeCloseTo(0.4);
    expect(worstMinutesSafety([0, 300], [null, null])).toBeNull();
    expect(worstMinutesSafety([], [])).toBeNull();
    expect(worstMinutesSafety([10], [0.3])).toBe(0.3);
  });
});

describe("population", () => {
  it("simulates a deterministic population in a plausible range", () => {
    const values = Array.from({ length: 200 }, (_, index) => simulatePopulation(`trip-${index}`));
    expect(simulatePopulation("trip-1")).toBe(values[1]);
    expect(Math.min(...values)).toBeGreaterThanOrEqual(500);
    expect(Math.max(...values)).toBeLessThanOrEqual(50_000);
    expect(new Set(values).size).toBeGreaterThan(150);
  });

  it("grows the bubble area with the population, within bounds", () => {
    expect(populationRadiusPx(0)).toBe(2.5);
    expect(populationRadiusPx(10_000)).toBeGreaterThan(populationRadiusPx(1_000));
    expect(populationRadiusPx(10_000_000)).toBe(16);
    expect(populationScale(500)).toBe(0);
    expect(populationScale(50_000)).toBe(1);
  });
});

describe("buildArrivals", () => {
  it("uses the provided population, sorts by arrival and colours by the lowest index", () => {
    const arrivals = buildArrivals([source("late", 900, [2.5, 48.9], 1_000), source("early", 300, [2.2, 48.8])]);
    expect(arrivals.map((arrival) => arrival.id)).toEqual(["early", "late"]);
    expect(arrivals[1]).toMatchObject({ population: 1_000, populationSimulated: false, implausible: false });
    expect(arrivals[1]?.worstMinutesSafety).toBeCloseTo(0.7);
    expect(arrivals[0]?.populationSimulated).toBe(true);
    expect(arrivals[0]?.color).toEqual(safetyIndexColor(arrivals[0]?.worstMinutesSafety ?? null));
  });

  it("marks trips longer than 2 hours as implausible, with a neutral colour", () => {
    const [arrival] = buildArrivals([source("long", 2 * 3600 + 1, [2.5, 48.9], 1_000)]);
    expect(arrival).toMatchObject({ implausible: true, worstMinutesSafety: null, color: rgba("neutral") });
  });

  it("colors contextual arrivals by the server's weighted score, not the local worst minutes", () => {
    const trip = source("weighted", 600, [2.5, 48.9]);
    const [arrival] = buildArrivals([{ ...trip, globalSafety: 0.25 }]);
    expect(arrival?.globalSafety).toBe(0.25);
    expect(arrival?.color).toEqual(safetyIndexColor(0.25));
    const [missing] = buildArrivals([{ ...trip, globalSafety: null }]);
    expect(missing?.color).toEqual(safetyIndexColor(null));
  });

  it("links each star to its nearest earlier neighbour", () => {
    const arrivals = buildArrivals([
      source("a", 100, [2.0, 48.0]),
      source("b", 200, [3.0, 49.0]),
      source("c", 300, [2.9, 48.9]),
      source("d", 400, [2.9, 48.9]),
    ]);
    expect(buildConstellation(arrivals)).toEqual([
      { from: [2.0, 48.0], to: [3.0, 49.0], time: 200 },
      { from: [3.0, 49.0], to: [2.9, 48.9], time: 300 },
      { from: [3.0, 49.0], to: [2.9, 48.9], time: 400 },
    ]);
  });

  it("counts reached items with a binary search", () => {
    const items = [{ time: 1 }, { time: 2 }, { time: 2 }, { time: 5 }];
    expect([0, 1, 2, 4, 5, 9].map((time) => countReached(items, time))).toEqual([0, 1, 3, 3, 4, 4]);
  });
});

describe("ArrivalTracker", () => {
  const arrivals = buildArrivals(Array.from({ length: 300 }, (_, index) => source(`t${index}`, 10 + index, [2.3, 48.8])));

  it("notifies and flashes new arrivals during playback", () => {
    const onArrive = vi.fn();
    const tracker = new ArrivalTracker(arrivals, onArrive);
    tracker.sync(0);
    tracker.update(11.5, 1000);
    expect(tracker.arrivedCount).toBe(2);
    expect(onArrive).toHaveBeenCalledOnce();
    expect(onArrive.mock.calls[0]?.[0]).toHaveLength(2);
    expect(tracker.activeFlashes(1000 + FLASH_DURATION_MS / 2).map((flash) => flash.progress)).toEqual([0.5, 0.5]);
    tracker.update(11.5, 1000 + FLASH_DURATION_MS);
    expect(tracker.activeFlashes(1000 + FLASH_DURATION_MS)).toEqual([]);
  });

  it("stays silent when syncing, seeking backwards or jumping far ahead", () => {
    const onArrive = vi.fn();
    const tracker = new ArrivalTracker(arrivals, onArrive);
    tracker.sync(50);
    expect(tracker.arrivedCount).toBe(41);
    tracker.update(20, 0);
    expect(tracker.arrivedCount).toBe(11);
    tracker.update(10_000, 0);
    expect(tracker.arrivedCount).toBe(300);
    expect(onArrive).not.toHaveBeenCalled();
    expect(tracker.activeFlashes(0)).toEqual([]);
  });
});
