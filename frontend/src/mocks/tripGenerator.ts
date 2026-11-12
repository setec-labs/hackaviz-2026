import type { JourneyDto, ScenarioDto } from "../api/contracts";
import type { GeoPoint } from "../domain/types";
import { createRandom, pickWeighted, randomBetween, type Random } from "./random";

/*
 * Generate synthetic trips as noisy curves between origins and destinations.
 * These paths do not follow the real transport network.
 */

/** Approximate bounds of Île-de-France. */
export const ILE_DE_FRANCE_BOUNDS = {
  minLongitude: 1.45,
  maxLongitude: 3.56,
  minLatitude: 48.12,
  maxLatitude: 49.24,
} as const;

/** Destination hubs used to give synthetic trips a plausible spatial structure. */
const DESTINATION_HUBS: readonly GeoPoint[] = [
  { latitude: 48.8924, longitude: 2.2369 }, // La Defense
  { latitude: 48.9362, longitude: 2.3574 }, // Saint-Denis
  { latitude: 48.7904, longitude: 2.4556 }, // Creteil
  { latitude: 48.8049, longitude: 2.1204 }, // Versailles
  { latitude: 48.7309, longitude: 2.2713 }, // Massy
  { latitude: 48.8924, longitude: 2.2069 }, // Nanterre
  { latitude: 48.8638, longitude: 2.4485 }, // Montreuil
  { latitude: 48.8473, longitude: 2.4397 }, // Vincennes
  { latitude: 48.7262, longitude: 2.3652 }, // Orly
  { latitude: 49.0097, longitude: 2.5479 }, // Roissy
  { latitude: 48.8448, longitude: 2.3735 }, // Gare de Lyon
  { latitude: 48.8809, longitude: 2.3553 }, // Gare du Nord
  { latitude: 48.8412, longitude: 2.3209 }, // Montparnasse
  { latitude: 48.8338, longitude: 2.2463 }, // Boulogne-Billancourt
  { latitude: 48.9472, longitude: 2.2507 }, // Argenteuil
  { latitude: 48.8495, longitude: 2.6510 }, // Marne-la-Vallee
  { latitude: 48.6315, longitude: 2.4402 }, // Evry
  { latitude: 49.0364, longitude: 2.0761 }, // Cergy
  { latitude: 48.8566, longitude: 2.3522 }, // Hotel de Ville
  { latitude: 48.8867, longitude: 2.3431 }, // Montmartre
];

interface ModeProfile {
  mode: string;
  speedKmh: number;
  maxDistanceKm: number;
  /** Probability of a stop at each segment, such as a light or bus stop. */
  stopProbability: number;
  stopSeconds: [number, number];
}

const MODES: readonly ModeProfile[] = [
  { mode: "walk", speedKmh: 4.8, maxDistanceKm: 5, stopProbability: 0.04, stopSeconds: [10, 40] },
  { mode: "bike", speedKmh: 15, maxDistanceKm: 14, stopProbability: 0.06, stopSeconds: [10, 45] },
  { mode: "night_bus", speedKmh: 22, maxDistanceKm: 45, stopProbability: 0.15, stopSeconds: [20, 60] },
  { mode: "car", speedKmh: 32, maxDistanceKm: 60, stopProbability: 0.05, stopSeconds: [15, 50] },
];

/** Parameters for reproducible synthetic trips from one origin. */
export interface MockTripOptions {
  origin: GeoPoint;
  tripCount: number;
  seed: number;
  /** Start of the departure window in epoch milliseconds. */
  windowStartMs?: number;
  /** Duration of the departure window in minutes. */
  departureWindowMinutes?: number;
}

/** November 10, 2026 at 22:00 Paris time, the default mock departure window. */
export const DEFAULT_NIGHT_START_MS = Date.parse("2026-11-10T22:00:00+01:00");

const KM_PER_DEGREE_LATITUDE = 110.574;

function kmPerDegreeLongitude(latitude: number): number {
  return 111.32 * Math.cos((latitude * Math.PI) / 180);
}

/** Approximate the distance between two nearby WGS84 positions in kilometres. */
export function distanceKm(a: GeoPoint, b: GeoPoint): number {
  const dx = (b.longitude - a.longitude) * kmPerDegreeLongitude((a.latitude + b.latitude) / 2);
  const dy = (b.latitude - a.latitude) * KM_PER_DEGREE_LATITUDE;
  return Math.hypot(dx, dy);
}

function offsetKm(point: GeoPoint, eastKm: number, northKm: number): GeoPoint {
  return {
    latitude: point.latitude + northKm / KM_PER_DEGREE_LATITUDE,
    longitude: point.longitude + eastKm / kmPerDegreeLongitude(point.latitude),
  };
}

function clampToRegion(point: GeoPoint): GeoPoint {
  const b = ILE_DE_FRANCE_BOUNDS;
  return {
    latitude: Math.min(b.maxLatitude, Math.max(b.minLatitude, point.latitude)),
    longitude: Math.min(b.maxLongitude, Math.max(b.minLongitude, point.longitude)),
  };
}

/** Approximate a Gaussian distribution using three centered uniform draws. */
function gaussian(random: Random): number {
  return (random() + random() + random() - 1.5) / 0.5;
}

function pickDestination(random: Random, start: GeoPoint): GeoPoint {
  const useHub = random() < 0.7;
  if (useHub) {
    const hub = DESTINATION_HUBS[Math.floor(random() * DESTINATION_HUBS.length)] ?? start;
    return clampToRegion(offsetKm(hub, gaussian(random) * 1.2, gaussian(random) * 1.2));
  }
  const angle = random() * Math.PI * 2;
  const radius = randomBetween(random, 1, 18);
  return clampToRegion(offsetKm(start, Math.cos(angle) * radius, Math.sin(angle) * radius));
}

function pickMode(random: Random, km: number): ModeProfile {
  const candidates = MODES.filter((profile) => km <= profile.maxDistanceKm);
  const pool = candidates.length > 0 ? candidates : MODES.slice(-1);
  return pickWeighted(
    random,
    pool.map((profile) => ({ value: profile, weight: profile.mode === "walk" ? 2 : 1 })),
  );
}

/** Create a noisy cubic Bézier curve to imitate a non-straight path. */
function buildPath(random: Random, start: GeoPoint, end: GeoPoint, km: number): GeoPoint[] {
  const dx = end.longitude - start.longitude;
  const dy = end.latitude - start.latitude;
  const bend1 = randomBetween(random, -0.35, 0.35);
  const bend2 = randomBetween(random, -0.35, 0.35);
  const control1 = { longitude: start.longitude + dx / 3 - dy * bend1, latitude: start.latitude + dy / 3 + dx * bend1 };
  const control2 = {
    longitude: start.longitude + (2 * dx) / 3 - dy * bend2,
    latitude: start.latitude + (2 * dy) / 3 + dx * bend2,
  };
  const pointCount = Math.round(Math.min(90, Math.max(10, km * 5)));
  const jitterKm = Math.min(0.08, km * 0.01);

  const points: GeoPoint[] = [];
  for (let i = 0; i < pointCount; i += 1) {
    const t = i / (pointCount - 1);
    const u = 1 - t;
    const base = {
      longitude:
        u * u * u * start.longitude + 3 * u * u * t * control1.longitude + 3 * u * t * t * control2.longitude + t * t * t * end.longitude,
      latitude:
        u * u * u * start.latitude + 3 * u * u * t * control1.latitude + 3 * u * t * t * control2.latitude + t * t * t * end.latitude,
    };
    const isEndpoint = i === 0 || i === pointCount - 1;
    points.push(isEndpoint ? base : offsetKm(base, gaussian(random) * jitterKm, gaussian(random) * jitterKm));
  }
  return points;
}

function buildJourney(random: Random, index: number, options: Required<MockTripOptions>): JourneyDto {
  // All trips in a scenario start at its origin, as in routing outputs.
  const start = clampToRegion(options.origin);
  let end = pickDestination(random, start);
  let km = distanceKm(start, end);
  if (km < 0.5) {
    end = offsetKm(start, 1.5, 0.8);
    km = distanceKm(start, end);
  }
  const profile = pickMode(random, km);
  const path = buildPath(random, start, end, km);

  const startMs = Math.round(options.windowStartMs + random() * options.departureWindowMinutes * 60_000);
  let currentMs = startMs;
  const coordinates: [number, number][] = [];
  const offsets: number[] = [];
  path.forEach((point, pointIndex) => {
    const previous = path[pointIndex - 1];
    if (previous) {
      const segmentKm = distanceKm(previous, point);
      const speedKmh = profile.speedKmh * randomBetween(random, 0.65, 1.25);
      currentMs += (segmentKm / speedKmh) * 3_600_000;
      if (random() < profile.stopProbability) {
        currentMs += randomBetween(random, ...profile.stopSeconds) * 1000;
      }
    }
    coordinates.push([Number(point.longitude.toFixed(6)), Number(point.latitude.toFixed(6))]);
    offsets.push(Math.round((currentMs - startMs) / 100) / 10);
  });

  const last = path[path.length - 1];
  const lastOffset = offsets[offsets.length - 1];
  if (!last || lastOffset === undefined) {
    throw new Error("Generated trip has no points");
  }
  const startTime = new Date(startMs).toISOString();
  const endTime = new Date(startMs + lastOffset * 1000).toISOString();
  return {
    journey_id: `mock-${options.seed}-${String(index).padStart(5, "0")}`,
    destination: {
      latitude: Number(last.latitude.toFixed(6)),
      longitude: Number(last.longitude.toFixed(6)),
      name: `Destination simulée ${index + 1}`,
    },
    start_time: startTime,
    end_time: endTime,
    legs: [
      {
        mode: profile.mode,
        start_time: startTime,
        end_time: endTime,
        from_stop: "ORIGIN",
        to_stop: "DESTINATION",
        gtfs_trip_id: null,
        point_range: [0, coordinates.length],
      },
    ],
    coordinates,
    offsets_s: offsets,
  };
}

/** Scenario metadata and synthetic trip generation options. */
export interface MockScenarioOptions extends MockTripOptions {
  id: string;
  name: string;
  description: string;
}

/** Generate a synthetic scenario in the routing `GET /scenarios/{id}` format. */
export function generateMockScenario(options: MockScenarioOptions): ScenarioDto {
  const resolved: Required<MockTripOptions> = {
    windowStartMs: DEFAULT_NIGHT_START_MS,
    departureWindowMinutes: 90,
    ...options,
  };
  const random = createRandom(resolved.seed);
  const journeys: JourneyDto[] = [];
  for (let i = 0; i < resolved.tripCount; i += 1) {
    journeys.push(buildJourney(random, i, resolved));
  }
  return {
    id: options.id,
    name: options.name,
    description: options.description,
    metadata_generated: false,
    origin: options.origin,
    departure_time: new Date(resolved.windowStartMs).toISOString(),
    journey_count: journeys.length,
    journeys,
  };
}
