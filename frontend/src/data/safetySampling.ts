import { isImplausibleTrip } from "../domain/tripPlausibility";
import type { GeoPoint, SafetyIndexValue, Trip } from "../domain/types";

/**
 * Temporary value for positions outside walking and waiting, not an actual
 * measurement: the lighting raster describes a pedestrian's environment.
 */
// TODO: query safety differently for non-pedestrian modes (vehicle or station indicators)
// and remove this placeholder.
export const NON_PEDESTRIAN_SAFETY_VALUE = 0.5;

/** Return whether a leg represents walking or waiting in public space. */
export function isPedestrianMode(mode: string): boolean {
  return mode === "wait" || mode === "walk" || mode.startsWith("walk_");
}

/** Apply the duration threshold to the trip's first and last timestamps. */
export function isImplausible(trip: Trip): boolean {
  const first = trip.timestampsMs[0] ?? 0;
  const last = trip.timestampsMs[trip.timestampsMs.length - 1] ?? first;
  return isImplausibleTrip((last - first) / 1000);
}

/**
 * Collect walking and waiting vertices from plausible trips in trip/vertex order.
 * Trips over two hours are displayed neutrally and are not evaluated.
 */
export function collectPedestrianPoints(trips: Trip[]): GeoPoint[] {
  const points: GeoPoint[] = [];
  for (const trip of trips) {
    if (isImplausible(trip)) continue;
    trip.path.forEach(([longitude, latitude], index) => {
      if (isPedestrianMode(trip.pointModes[index] ?? "")) points.push({ latitude, longitude });
    });
  }
  return points;
}

/**
 * Reconstruct one index per vertex in trip/vertex order.
 *
 * @param pedestrianValues - Values in {@link collectPedestrianPoints} order, or
 * null after a safety service failure. Pedestrian values then remain unavailable;
 * implausible trips always have null values.
 */
export function mergeSafetyValues(trips: Trip[], pedestrianValues: SafetyIndexValue[] | null): SafetyIndexValue[] {
  const values: SafetyIndexValue[] = [];
  let cursor = 0;
  for (const trip of trips) {
    if (isImplausible(trip)) {
      for (let index = 0; index < trip.path.length; index += 1) values.push(null);
      continue;
    }
    trip.path.forEach((_point, index) => {
      if (isPedestrianMode(trip.pointModes[index] ?? "")) {
        values.push(pedestrianValues ? (pedestrianValues[cursor] ?? null) : null);
        cursor += 1;
      } else {
        values.push(NON_PEDESTRIAN_SAFETY_VALUE);
      }
    });
  }
  return values;
}
