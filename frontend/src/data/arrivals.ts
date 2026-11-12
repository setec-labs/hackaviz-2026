import { safetyIndexColor } from "../domain/safetyLevels";
import type { SafetyIndexValue } from "../domain/types";
import type { Rgba } from "../theme/palette";

/** Fenetre, en secondes simulees avant l'arrivee, sur laquelle on retient l'anxiete maximale. */
export const ARRIVAL_WINDOW_SECONDS = 10 * 60;

const SIMULATED_POPULATION_MIN = 500;
const SIMULATED_POPULATION_MAX = 50_000;
/** Nombre d'arrivees precedentes examinees pour relier une etoile a sa plus proche voisine. */
const CONSTELLATION_LOOKBACK = 300;

export interface ArrivalSource {
  id: string;
  destinationName: string | null;
  destinationPopulation: number | null;
  path: [number, number][];
  timestamps: number[];
  safety: SafetyIndexValue[];
  endTime: number;
}

export interface Arrival {
  id: string;
  destinationName: string | null;
  position: [number, number];
  /** Instant d'arrivee, en secondes relatives au debut du jeu de donnees. */
  time: number;
  population: number;
  /** Vrai tant que la population n'est pas fournie par les donnees. */
  populationSimulated: boolean;
  /** Indice le plus bas (anxiete maximale = 1 - indice) sur les 10 dernieres minutes ; null sans donnee. */
  lowestSafety: SafetyIndexValue;
  radiusPx: number;
  color: Rgba;
}

export interface ConstellationLink {
  from: [number, number];
  to: [number, number];
  /** Apparition du lien : arrivee de l'etoile la plus recente. */
  time: number;
}

/** Indice le plus defavorable parmi les positions des `windowSeconds` precedant l'arrivee. */
export function lowestSafetyBeforeArrival(
  timestamps: number[],
  safety: SafetyIndexValue[],
  endTime: number,
  windowSeconds = ARRIVAL_WINDOW_SECONDS,
): SafetyIndexValue {
  let lowest: number | null = null;
  timestamps.forEach((timestamp, index) => {
    const value = safety[index] ?? null;
    if (timestamp >= endTime - windowSeconds && value !== null) {
      lowest = lowest === null ? value : Math.min(lowest, value);
    }
  });
  return lowest;
}

function hashString(text: string): number {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(i), 16777619);
  }
  // Finaliseur murmur3 : disperse les identifiants voisins (`trip-1`, `trip-2`...).
  hash = Math.imul(hash ^ (hash >>> 16), 0x85ebca6b);
  hash = Math.imul(hash ^ (hash >>> 13), 0xc2b2ae35);
  return (hash ^ (hash >>> 16)) >>> 0;
}

// TODO: remplacer par `destination.population` des que le pipeline routing la fournit.
/** Population simulee, deterministe pour un identifiant, repartie logarithmiquement. */
export function simulatePopulation(seedText: string): number {
  const unit = hashString(seedText) / 0xffffffff;
  const value = SIMULATED_POPULATION_MIN * (SIMULATED_POPULATION_MAX / SIMULATED_POPULATION_MIN) ** unit;
  return Math.round(value / 10) * 10;
}

/** Rayon proportionnel a la racine de la population : l'aire de la bulle suit la population. */
export function populationRadiusPx(population: number): number {
  return Math.min(22, Math.max(3, 3 + Math.sqrt(population) * 0.07));
}

/** Position relative de la population entre les bornes simulees (0 = petite zone, 1 = grande). */
export function populationScale(population: number): number {
  const ratio = Math.log(Math.max(population, 1) / SIMULATED_POPULATION_MIN) /
    Math.log(SIMULATED_POPULATION_MAX / SIMULATED_POPULATION_MIN);
  return Math.min(1, Math.max(0, ratio));
}

/** Arrivees triees par instant d'arrivee. */
export function buildArrivals(trips: ArrivalSource[]): Arrival[] {
  const arrivals = trips.flatMap((trip): Arrival[] => {
    const position = trip.path[trip.path.length - 1];
    if (!position) return [];
    const populationSimulated = trip.destinationPopulation === null;
    const population = trip.destinationPopulation ?? simulatePopulation(trip.id);
    const lowestSafety = lowestSafetyBeforeArrival(trip.timestamps, trip.safety, trip.endTime);
    return [{
      id: trip.id,
      destinationName: trip.destinationName,
      position,
      time: trip.endTime,
      population,
      populationSimulated,
      lowestSafety,
      radiusPx: populationRadiusPx(population),
      color: safetyIndexColor(lowestSafety),
    }];
  });
  return arrivals.sort((a, b) => a.time - b.time);
}

/** Relie chaque etoile a la plus proche des etoiles deja apparues, pour former une constellation. */
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

/** Nombre d'elements d'un tableau trie par `time` dont l'instant est atteint a `time`. */
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
