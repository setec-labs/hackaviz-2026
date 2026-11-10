import type { RenderDataset } from "../data/prepareDataset";

/**
 * Positions courantes ("tetes") des trajets actifs, calculees a chaque image dans des
 * tableaux types preallouees puis transmises a deck.gl sous forme d'attributs binaires.
 * Aucune allocation d'objet par trajet et par image.
 */
export class HeadBuffers {
  readonly positions: Float32Array;
  readonly colors: Uint8Array;
  readonly radii: Float32Array;
  /** Index du trajet source dans `dataset.trips`, pour l'infobulle. */
  readonly tripIndices: Int32Array;
  /** Indice au point courant (NaN si non disponible). */
  readonly safety: Float32Array;
  count = 0;

  constructor(capacity: number) {
    this.positions = new Float32Array(capacity * 2);
    this.colors = new Uint8Array(capacity * 4);
    this.radii = new Float32Array(capacity);
    this.tripIndices = new Int32Array(capacity);
    this.safety = new Float32Array(capacity);
  }

  update(dataset: RenderDataset, time: number): number {
    let count = 0;
    dataset.trips.forEach((trip, tripIndex) => {
      if (time < trip.startTime || time > trip.endTime) {
        return;
      }
      const { timestamps, path } = trip;
      const segment = findSegment(timestamps, time);
      const t0 = timestamps[segment] ?? time;
      const t1 = timestamps[segment + 1] ?? t0;
      const ratio = t1 > t0 ? (time - t0) / (t1 - t0) : 0;
      const from = path[segment];
      const to = path[segment + 1] ?? from;
      if (!from || !to) {
        return;
      }
      const vertex = ratio < 0.5 ? segment : segment + 1;
      const color = trip.colors[vertex] ?? trip.colors[segment];
      const value = trip.safety[vertex] ?? null;

      this.positions[count * 2] = from[0] + (to[0] - from[0]) * ratio;
      this.positions[count * 2 + 1] = from[1] + (to[1] - from[1]) * ratio;
      if (color) {
        this.colors.set(color, count * 4);
      }
      this.radii[count] = trip.markerRadii[vertex] ?? 3;
      this.tripIndices[count] = tripIndex;
      this.safety[count] = value ?? Number.NaN;
      count += 1;
    });
    this.count = count;
    return count;
  }
}

/** Plus grand index i tel que timestamps[i] <= time (recherche dichotomique). */
export function findSegment(timestamps: readonly number[], time: number): number {
  let low = 0;
  let high = timestamps.length - 1;
  while (low < high) {
    const middle = (low + high + 1) >> 1;
    if ((timestamps[middle] ?? Number.POSITIVE_INFINITY) <= time) {
      low = middle;
    } else {
      high = middle - 1;
    }
  }
  return Math.min(low, Math.max(0, timestamps.length - 2));
}
