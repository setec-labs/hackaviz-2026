import { isImplausibleTrip } from "../domain/tripPlausibility";
import type { GeoPoint, SafetyIndexValue, Trip } from "../domain/types";

/**
 * Valeur provisoire attribuee aux positions hors marche et attente (transport en commun, velo...).
 * Ce n'est pas une mesure : le raster d'eclairage ne decrit que l'environnement d'un pieton.
 */
// TODO: interroger plus tard le service safety autrement pour les modes autres que la marche et
// l'attente (indicateurs propres aux vehicules, aux stations...), puis supprimer cette valeur.
export const NON_PEDESTRIAN_SAFETY_VALUE = 0.5;

/** Vrai pour les troncons ou l'usager est a pied dans l'espace public : marche et attente. */
export function isPedestrianMode(mode: string): boolean {
  return mode === "wait" || mode === "walk" || mode.startsWith("walk_");
}

export function isImplausible(trip: Trip): boolean {
  const first = trip.timestampsMs[0] ?? 0;
  const last = trip.timestampsMs[trip.timestampsMs.length - 1] ?? first;
  return isImplausibleTrip((last - first) / 1000);
}

/**
 * Positions a envoyer au service safety : uniquement celles des troncons de marche et d'attente
 * des trajets plausibles (les trajets de plus de 2 h sont affiches en couleur neutre).
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
 * Reconstitue un indice par sommet, dans l'ordre des trajets puis des positions.
 * `pedestrianValues` suit l'ordre de `collectPedestrianPoints` ; null si le service a echoue,
 * auquel cas les positions pietonnes restent « non disponibles ». Les trajets peu plausibles
 * ne sont pas evalues : leurs positions valent null.
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
