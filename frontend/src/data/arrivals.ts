import { safetyIndexColor } from "../domain/safetyLevels";
import { implausibleTripColor, isImplausibleTrip } from "../domain/tripPlausibility";
import type { SafetyIndexValue } from "../domain/types";
import type { Rgba } from "../theme/palette";

/** Duree cumulee, en secondes simulees, des pires instants du trajet retenus pour l'anxiete. */
export const ANXIETY_WORST_SECONDS = 10 * 60;
/** Pas d'echantillonnage temporel de l'indice le long du trajet. */
const SAMPLE_STEP_SECONDS = 15;

const SIMULATED_POPULATION_MIN = 500;
const SIMULATED_POPULATION_MAX = 50_000;
/** Nombre d'arrivees precedentes examinees pour relier une etoile a sa plus proche voisine. */
const CONSTELLATION_LOOKBACK = 300;
// Bornes reduites pour rester lisible avec ~1 300 arrivees par scenario.
const MIN_BUBBLE_RADIUS_PX = 2.5;
const MAX_BUBBLE_RADIUS_PX = 16;

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
  /**
   * Indice moyen des 10 pires minutes du trajet, consecutives ou non (anxiete = 1 - indice) ;
   * null sans donnee ou si le trajet est peu plausible.
   */
  worstMinutesSafety: SafetyIndexValue;
  /** Trajet de plus de 2 h : bulle neutre et creuse. */
  implausible: boolean;
  radiusPx: number;
  color: Rgba;
}

export interface ConstellationLink {
  from: [number, number];
  to: [number, number];
  /** Apparition du lien : arrivee de l'etoile la plus recente. */
  time: number;
}

function segmentValue(a: SafetyIndexValue, b: SafetyIndexValue): SafetyIndexValue {
  if (a === null) return b;
  if (b === null) return a;
  return (a + b) / 2;
}

/**
 * Indice moyen des `minutesSeconds` les plus defavorables du trajet, consecutives ou non (ramenees a la
 * duree du trajet s'il est plus court). L'indice est echantillonne tous les 15 s ; chaque segment prend
 * la moyenne des valeurs disponibles a ses extremites et les instants sans donnee sont ignores.
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
  // Finaliseur murmur3 : disperse les identifiants voisins (`trip-1`, `trip-2`...).
  hash = Math.imul(hash ^ (hash >>> 16), 0x85ebca6b);
  hash = Math.imul(hash ^ (hash >>> 13), 0xc2b2ae35);
  return (hash ^ (hash >>> 16)) >>> 0;
}

// Repli pour les donnees sans `destination.population` (mocks) ; le pipeline routing la fournit.
/** Population simulee, deterministe pour un identifiant, repartie logarithmiquement. */
export function simulatePopulation(seedText: string): number {
  const unit = hashString(seedText) / 0xffffffff;
  const value = SIMULATED_POPULATION_MIN * (SIMULATED_POPULATION_MAX / SIMULATED_POPULATION_MIN) ** unit;
  return Math.round(value / 10) * 10;
}

/** Rayon proportionnel a la racine de la population : l'aire de la bulle suit la population. */
export function populationRadiusPx(population: number): number {
  return Math.min(MAX_BUBBLE_RADIUS_PX, Math.max(MIN_BUBBLE_RADIUS_PX, 2 + Math.sqrt(population) * 0.04));
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
    const implausible = isImplausibleTrip(trip.endTime - (trip.timestamps[0] ?? trip.endTime));
    const worst = implausible ? null : worstMinutesSafety(trip.timestamps, trip.safety);
    return [{
      id: trip.id,
      destinationName: trip.destinationName,
      position,
      time: trip.endTime,
      population,
      populationSimulated,
      worstMinutesSafety: worst,
      implausible,
      radiusPx: populationRadiusPx(population),
      color: implausible ? implausibleTripColor() : safetyIndexColor(worst),
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
