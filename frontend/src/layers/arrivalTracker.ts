import { countReached, type Arrival } from "../data/arrivals";

/** Duree du flash d'apparition, en millisecondes reelles (independante de la vitesse). */
export const FLASH_DURATION_MS = 1400;
/** Au-dela, un saut dans la timeline affiche les bulles sans flash ni son. */
const MAX_ARRIVALS_PER_FRAME = 200;
const MAX_FLASHES = 40;

export interface ArrivalFlash {
  arrival: Arrival;
  /** Avancement du flash, de 0 (apparition) a 1 (fin). */
  progress: number;
}

/**
 * Suit les arrivees atteintes par l'horloge, image par image, pour animer les nouvelles
 * bulles et signaler leur apparition (son). Un retour en arriere efface les flashs en cours.
 */
export class ArrivalTracker {
  private reached = 0;
  private flashes: { arrival: Arrival; startMs: number }[] = [];

  constructor(
    private readonly arrivals: readonly Arrival[],
    private readonly onArrive: (fresh: Arrival[]) => void = () => {},
  ) {}

  get arrivedCount(): number {
    return this.reached;
  }

  /** Se place a `time` sans flash ni notification (ouverture d'un scenario). */
  sync(time: number): void {
    this.reached = countReached(this.arrivals, time);
    this.flashes = [];
  }

  update(time: number, nowMs: number): void {
    const next = countReached(this.arrivals, time);
    if (next > this.reached && next - this.reached <= MAX_ARRIVALS_PER_FRAME) {
      const fresh = this.arrivals.slice(this.reached, next);
      for (const arrival of fresh.slice(-MAX_FLASHES)) this.flashes.push({ arrival, startMs: nowMs });
      this.onArrive(fresh);
    } else if (next < this.reached) {
      this.flashes = [];
    }
    this.reached = next;
    this.flashes = this.flashes
      .filter((flash) => nowMs - flash.startMs < FLASH_DURATION_MS)
      .slice(-MAX_FLASHES);
  }

  activeFlashes(nowMs: number): ArrivalFlash[] {
    return this.flashes.map(({ arrival, startMs }) => ({
      arrival,
      progress: Math.min(1, Math.max(0, (nowMs - startMs) / FLASH_DURATION_MS)),
    }));
  }
}
