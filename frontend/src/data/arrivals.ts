import { safetyIndexColor } from "../domain/safetyLevels";
import { implausibleTripColor, isImplausibleTrip } from "../domain/tripPlausibility";
import type { SafetyIndexValue } from "../domain/types";
import type { Rgba } from "../theme/palette";

/** Total simulated duration of the worst samples retained for anxiety. */
export const ANXIETY_WORST_SECONDS = 10 * 60;
/** Temporal sampling interval for the index along a trip. */
const SAMPLE_STEP_SECONDS = 15;

const SIMULATED_POPULATION_MIN = 500;
const SIMULATED_POPULATION_MAX = 50_000;
/** Maximum number of previous arrivals considered when linking a star. */
const CONSTELLATION_LOOKBACK = 300;
// Keep bubbles legible when a scenario has approximately 1,300 arrivals.
const MIN_BUBBLE_RADIUS_PX = 2.5;
const MAX_BUBBLE_RADIUS_PX = 16;

/** Render trip data needed to build an arrival. Times are relative seconds. */
export interface ArrivalSource {
  id: string;
  destinationName: string | null;
  destinationPopulation: number | null;
  path: [number, number][];
  timestamps: number[];
  safety: SafetyIndexValue[];
  globalSafety?: SafetyIndexValue;
  endTime: number;
}

/** Arrival bubble data, including population provenance and visual attributes. */
export interface Arrival {
  id: string;
  destinationName: string | null;
  position: [number, number];
  /** Arrival time in seconds relative to the dataset origin. */
  time: number;
  population: number;
  /** Whether population was simulated because the source did not provide it. */
  populationSimulated: boolean;
  /**
   * Mean index over the ten worst minutes, consecutive or not (anxiety is
   * 1 minus this value); null if unavailable or the trip is implausible.
   */
  worstMinutesSafety: SafetyIndexValue;
  /** Weighted mean of applicable indicator means, computed by the safety service. */
  globalSafety?: SafetyIndexValue;
  /** Whether the trip exceeds two hours and uses a neutral, hollow bubble. */
  implausible: boolean;
  radiusPx: number;
  color: Rgba;
}

/** Link between two arrivals, visible from the later arrival time. */
export interface ConstellationLink {
  from: [number, number];
  to: [number, number];
  /** Appearance time of the more recent arrival. */
  time: number;
}

function segmentValue(a: SafetyIndexValue, b: SafetyIndexValue): SafetyIndexValue {
  if (a === null) return b;
  if (b === null) return a;
  return (a + b) / 2;
}

/**
 * Average the lowest available samples across the requested duration, whether
 * consecutive or not. Samples are taken every 15 seconds using the mean of
 * available segment endpoints; samples without data are ignored.
 *
 * @param timestamps - Vertex times in seconds.
 * @param safety - Index values aligned with the vertex times.
 * @param minutesSeconds - Duration of worst samples to retain, in seconds.
 * @returns The mean of available worst samples, or null when none are available.
 */
export function worstMinutesSafety(
  timestamps: number[],
  safety: SafetyIndexValue[],
  minutesSeconds = ANXIETY_WORST_SECONDS,
): SafetyIndexValue {
  const start = timestamps[0];
  const end = timestamps[timestamps.length - 1];
  if (start === undefined || end === undefined) return null;
  const sampleCount = Math.max(1, Math.ceil((end - start) / SAMPLE_STEP_SECONDS));
  const samples: number[] = [];
  let segment = 0;
  for (let k = 0; k < sampleCount; k += 1) {
    const time = Math.min(end, start + (k + 0.5) * SAMPLE_STEP_SECONDS);
    while (segment < timestamps.length - 2 && (timestamps[segment + 1] ?? end) < time) segment += 1;
    const last = timestamps.length === 1;
    const value = last ? (safety[0] ?? null) : segmentValue(safety[segment] ?? null, safety[segment + 1] ?? null);
    if (value !== null) samples.push(value);
  }
  if (samples.length === 0) return null;

  const worstCount = Math.min(samples.length, Math.max(1, Math.round(minutesSeconds / SAMPLE_STEP_SECONDS)));
  samples.sort((a, b) => a - b);
  let sum = 0;
  for (let k = 0; k < worstCount; k += 1) sum += samples[k] ?? 0;
  return sum / worstCount;
}

function hashString(text: string): number {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(i), 16777619);
  }
  // Murmur3 finalizer disperses neighboring identifiers such as trip-1 and trip-2.
  hash = Math.imul(hash ^ (hash >>> 16), 0x85ebca6b);
  hash = Math.imul(hash ^ (hash >>> 13), 0xc2b2ae35);
  return (hash ^ (hash >>> 16)) >>> 0;
}

/** Simulate a deterministic, log-distributed population when source data is absent. */
export function simulatePopulation(seedText: string): number {
  const unit = hashString(seedText) / 0xffffffff;
  const value = SIMULATED_POPULATION_MIN * (SIMULATED_POPULATION_MAX / SIMULATED_POPULATION_MIN) ** unit;
  return Math.round(value / 10) * 10;
}

/** Scale bubble radius with the square root of population, within display bounds. */
export function populationRadiusPx(population: number): number {
  return Math.min(MAX_BUBBLE_RADIUS_PX, Math.max(MIN_BUBBLE_RADIUS_PX, 2 + Math.sqrt(population) * 0.04));
}

/** Return a clamped logarithmic population scale between the simulated bounds. */
export function populationScale(population: number): number {
  const ratio = Math.log(Math.max(population, 1) / SIMULATED_POPULATION_MIN) /
    Math.log(SIMULATED_POPULATION_MAX / SIMULATED_POPULATION_MIN);
  return Math.min(1, Math.max(0, ratio));
}

/** Build arrivals sorted by time, marking populations simulated when absent. */
export function buildArrivals(trips: ArrivalSource[]): Arrival[] {
  const arrivals = trips.flatMap((trip): Arrival[] => {
    const position = trip.path[trip.path.length - 1];
    if (!position) return [];
    const populationSimulated = trip.destinationPopulation === null;
    const population = trip.destinationPopulation ?? simulatePopulation(trip.id);
    const implausible = isImplausibleTrip(trip.endTime - (trip.timestamps[0] ?? trip.endTime));
    const worst = implausible ? null : worstMinutesSafety(trip.timestamps, trip.safety);
    const global = implausible ? null : trip.globalSafety;
    return [{
      id: trip.id,
      destinationName: trip.destinationName,
      position,
      time: trip.endTime,
      population,
      populationSimulated,
      worstMinutesSafety: worst,
      globalSafety: global,
      implausible,
      radiusPx: populationRadiusPx(population),
      color: implausible ? implausibleTripColor() : safetyIndexColor(global === undefined ? worst : global),
    }];
  });
  return arrivals.sort((a, b) => a.time - b.time);
}

/** Connect each arrival to its nearest distinct-position neighbor among the previous 300 arrivals. */
export function buildConstellation(arrivals: Arrival[]): ConstellationLink[] {
  const links: ConstellationLink[] = [];
  arrivals.forEach((arrival, index) => {
    const [longitude, latitude] = arrival.position;
    const cosLatitude = Math.cos((latitude * Math.PI) / 180);
    let nearest: Arrival | null = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (let previous = Math.max(0, index - CONSTELLATION_LOOKBACK); previous < index; previous += 1) {
      const candidate = arrivals[previous];
      if (!candidate) continue;
      const dx = (candidate.position[0] - longitude) * cosLatitude;
      const dy = candidate.position[1] - latitude;
      const distance = dx * dx + dy * dy;
      if (distance > 0 && distance < nearestDistance) {
        nearest = candidate;
        nearestDistance = distance;
      }
    }
    if (nearest) links.push({ from: nearest.position, to: arrival.position, time: arrival.time });
  });
  return links;
}

/** Count entries in time order whose time is at or before the supplied time. */
export function countReached(items: readonly { time: number }[], time: number): number {
  let low = 0;
  let high = items.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if ((items[middle]?.time ?? Number.POSITIVE_INFINITY) <= time) low = middle + 1;
    else high = middle;
  }
  return low;
}
