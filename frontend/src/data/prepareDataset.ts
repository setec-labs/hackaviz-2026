import type { SafetyIndexValue, Trip } from "../domain/types";
import { classifySafetyIndex, safetyIndexColor } from "../domain/safetyLevels";
import type { Rgba } from "../theme/palette";

/** Trajet pret a etre rendu par deck.gl (temps en secondes relatives a `originMs`). */
export interface RenderTrip {
  id: string;
  destinationName: string | null;
  mode: string | null;
  path: [number, number][];
  /** Secondes depuis `RenderDataset.originMs` (Float32 cote GPU : rester sur des valeurs moderees). */
  timestamps: number[];
  /** Indice par sommet ; null si indisponible ou si le service indice a echoue. */
  safety: SafetyIndexValue[];
  /** Couleur par sommet derivee de l'indice. */
  colors: Rgba[];
  /** Rayon du marqueur par sommet, derive du niveau d'indicateur. */
  markerRadii: number[];
  startTime: number;
  endTime: number;
}

export interface RenderDataset {
  trips: RenderTrip[];
  /** Instant de reference (ms epoch) correspondant au temps simule 0. */
  originMs: number;
  startTime: number;
  endTime: number;
}

/**
 * Combine les trajets et les indices (aplatis dans l'ordre des sommets) en un jeu
 * de donnees de rendu. `safetyValues` vaut null si l'indice n'a pas pu etre charge.
 */
export function prepareDataset(trips: Trip[], safetyValues: SafetyIndexValue[] | null): RenderDataset {
  const originMs = trips.reduce((min, trip) => Math.min(min, trip.startTimeMs), Number.POSITIVE_INFINITY);
  if (!Number.isFinite(originMs)) {
    return { trips: [], originMs: 0, startTime: 0, endTime: 0 };
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
    return {
      id: trip.id,
      destinationName: trip.destinationName,
      mode: trip.mode,
      path: trip.path,
      timestamps,
      safety,
      colors: safety.map((value) => safetyIndexColor(value)),
      markerRadii: safety.map((value) => classifySafetyIndex(value).markerRadiusPx),
      startTime,
      endTime: tripEnd,
    };
  });

  return { trips: renderTrips, originMs, startTime: 0, endTime };
}

export function countActiveTrips(dataset: RenderDataset, time: number): number {
  let count = 0;
  for (const trip of dataset.trips) {
    if (time >= trip.startTime && time <= trip.endTime) {
      count += 1;
    }
  }
  return count;
}
