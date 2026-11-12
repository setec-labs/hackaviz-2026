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

/** Positions a envoyer au service safety : uniquement celles des troncons de marche et d'attente. */
export function collectPedestrianPoints(trips: Trip[]): GeoPoint[] {
  const points: GeoPoint[] = [];
  for (const trip of trips) {
    trip.path.forEach(([longitude, latitude], index) => {
      if (isPedestrianMode(trip.pointModes[index] ?? "")) points.push({ latitude, longitude });
    });
  }
  return points;
}

/**
 * Reconstitue un indice par sommet, dans l'ordre des trajets puis des positions.
 * `pedestrianValues` suit l'ordre de `collectPedestrianPoints` ; null si le service a echoue,
 * auquel cas les positions pietonnes restent « non disponibles ».
 */
export function mergeSafetyValues(trips: Trip[], pedestrianValues: SafetyIndexValue[] | null): SafetyIndexValue[] {
  const values: SafetyIndexValue[] = [];
  let cursor = 0;
  for (const trip of trips) {
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
