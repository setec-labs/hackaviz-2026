import { countReached, type Arrival } from "../data/arrivals";

/** Flash duration in real milliseconds, independent of simulation speed. */
export const FLASH_DURATION_MS = 1400;
/** Larger timeline jumps show arrivals without flashes or sound. */
const MAX_ARRIVALS_PER_FRAME = 200;
const MAX_FLASHES = 40;

/** A new arrival and the progress of its appearance flash. */
export interface ArrivalFlash {
  arrival: Arrival;
  /** Flash progress from 0 (start) to 1 (end). */
  progress: number;
}

/**
 * Track arrivals reached by the clock and notify listeners of new arrivals.
 * Rewinding clears active flashes; large forward jumps suppress flashes and sound.
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

  /** Synchronize to a time without flashes or notifications. */
  sync(time: number): void {
    this.reached = countReached(this.arrivals, time);
    this.flashes = [];
  }

  /** Update reached arrivals and expire flashes at the given simulation and real times. */
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

  /** Return flash progress at the given real time in milliseconds. */
  activeFlashes(nowMs: number): ArrivalFlash[] {
    return this.flashes.map(({ arrival, startMs }) => ({
      arrival,
      progress: Math.min(1, Math.max(0, (nowMs - startMs) / FLASH_DURATION_MS)),
    }));
  }
}
