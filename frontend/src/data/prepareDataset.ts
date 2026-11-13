import type { SafetyIndexValue, Trip } from "../domain/types";
import { classifySafetyIndex, safetyIndexColor } from "../domain/safetyLevels";
import { implausibleTripColor, isImplausibleTrip } from "../domain/tripPlausibility";
import type { Rgba } from "../theme/palette";
import { buildArrivals, buildConstellation, type Arrival, type ConstellationLink } from "./arrivals";

/** A deck.gl-ready trip with times in seconds relative to the dataset origin. */
export interface RenderTrip {
  id: string;
  destinationName: string | null;
  destinationPopulation: number | null;
  mode: string | null;
  path: [number, number][];
  /** Seconds since `RenderDataset.originMs`, kept small for GPU Float32 precision. */
  timestamps: number[];
  /** Index per vertex; null if unavailable or if the index service failed. */
  safety: SafetyIndexValue[];
  /** Server-computed global weighted score, when contextual evaluation was requested. */
  globalSafety?: SafetyIndexValue;
  /** Whether the trip exceeds two hours and is displayed neutrally. */
  implausible: boolean;
  /** Color per vertex, neutral for implausible trips. */
  colors: Rgba[];
  /** Marker radius per vertex, derived from the index level. */
  markerRadii: number[];
  startTime: number;
  endTime: number;
}

/** Precomputed trip, arrival and constellation data for the rendering layers. */
export interface RenderDataset {
  trips: RenderTrip[];
  /** Arrival bubbles sorted by arrival time. */
  arrivals: Arrival[];
  /** Constellation links sorted by appearance time. */
  constellation: ConstellationLink[];
  /** Reference epoch timestamp in milliseconds for simulated time zero. */
  originMs: number;
  startTime: number;
  endTime: number;
}

/**
 * Prepare trip colors, relative times, arrivals and links for rendering.
 *
 * @param trips - Journeys in display order.
 * @param safetyValues - Indices flattened in trip/vertex order, or null on failure.
 */
export function prepareDataset(
  trips: Trip[],
  safetyValues: SafetyIndexValue[] | null,
  journeyScores?: ReadonlyMap<string, SafetyIndexValue>,
): RenderDataset {
  const originMs = trips.reduce((min, trip) => Math.min(min, trip.startTimeMs), Number.POSITIVE_INFINITY);
  if (!Number.isFinite(originMs)) {
    return { trips: [], arrivals: [], constellation: [], originMs: 0, startTime: 0, endTime: 0 };
  }

  let cursor = 0;
  let endTime = 0;
  const renderTrips = trips.map((trip): RenderTrip => {
    const timestamps = trip.timestampsMs.map((ms) => (ms - originMs) / 1000);
    const safety = trip.path.map((): SafetyIndexValue => {
      const value = safetyValues ? (safetyValues[cursor] ?? null) : null;
      cursor += 1;
      return value;
    });
    const startTime = timestamps[0] ?? 0;
    const tripEnd = timestamps[timestamps.length - 1] ?? startTime;
    endTime = Math.max(endTime, tripEnd);
    const implausible = isImplausibleTrip(tripEnd - startTime);
    return {
      id: trip.id,
      destinationName: trip.destinationName,
      destinationPopulation: trip.destinationPopulation,
      mode: trip.mode,
      path: trip.path,
      timestamps,
      safety,
      globalSafety: journeyScores ? (journeyScores.get(trip.id) ?? null) : undefined,
      implausible,
      colors: safety.map((value) => (implausible ? implausibleTripColor(150) : safetyIndexColor(value))),
      markerRadii: safety.map((value) => classifySafetyIndex(value).markerRadiusPx),
      startTime,
      endTime: tripEnd,
    };
  });

  const arrivals = buildArrivals(renderTrips);
  return { trips: renderTrips, arrivals, constellation: buildConstellation(arrivals), originMs, startTime: 0, endTime };
}

/** Count trips active at the given relative simulation time in seconds. */
export function countActiveTrips(dataset: RenderDataset, time: number): number {
  let count = 0;
  for (const trip of dataset.trips) {
    if (time >= trip.startTime && time <= trip.endTime) {
      count += 1;
    }
  }
  return count;
}
