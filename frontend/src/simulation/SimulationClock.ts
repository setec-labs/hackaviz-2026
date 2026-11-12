/**
 * Shared simulation clock for all animated layers.
 *
 * Time is expressed in dataset-relative seconds. One animation-frame loop
 * notifies `onFrame` listeners every frame and React subscribers less often.
 */

/** Immutable clock state exposed to React subscribers. */
export interface ClockSnapshot {
  currentTime: number;
  startTime: number;
  endTime: number;
  isPlaying: boolean;
  /** Number of real seconds per simulated hour. */
  realSecondsPerSimHour: number;
}

/** Animation-frame scheduler, injectable for tests. */
export interface FrameScheduler {
  request(callback: (timestampMs: number) => void): number;
  cancel(handle: number): void;
}

/** Optional playback speed, UI notification interval and frame scheduler. */
export interface SimulationClockOptions {
  realSecondsPerSimHour?: number;
  /** Minimum real milliseconds between React notifications during playback. */
  uiIntervalMs?: number;
  scheduler?: FrameScheduler;
}

/** Prevents a large simulated-time jump after a tab returns from the background. */
const MAX_FRAME_DELTA_MS = 250;

const browserScheduler: FrameScheduler = {
  request: (callback) => requestAnimationFrame(callback),
  cancel: (handle) => cancelAnimationFrame(handle),
};

/** Drive playback and publish animation frames and throttled UI snapshots. */
export class SimulationClock {
  private currentTime = 0;
  private startTime = 0;
  private endTime = 0;
  private isPlaying = false;
  private realSecondsPerSimHour: number;
  private readonly uiIntervalMs: number;
  private readonly scheduler: FrameScheduler;

  private frameHandle: number | null = null;
  private lastFrameMs: number | null = null;
  private lastUiNotifyMs = 0;
  private snapshot: ClockSnapshot;

  private readonly frameListeners = new Set<(time: number) => void>();
  private readonly uiListeners = new Set<() => void>();

  constructor(options: SimulationClockOptions = {}) {
    this.realSecondsPerSimHour = options.realSecondsPerSimHour ?? 60;
    this.uiIntervalMs = options.uiIntervalMs ?? 100;
    this.scheduler = options.scheduler ?? browserScheduler;
    this.snapshot = this.buildSnapshot();
  }

  /** Simulated seconds elapsed per real second. */
  get rate(): number {
    return 3600 / this.realSecondsPerSimHour;
  }

  get time(): number {
    return this.currentTime;
  }

  /** Return the latest UI snapshot for `useSyncExternalStore`. */
  getSnapshot = (): ClockSnapshot => this.snapshot;

  /** Subscribe to UI updates and return an unsubscribe callback. */
  subscribe = (listener: () => void): (() => void) => {
    this.uiListeners.add(listener);
    return () => this.uiListeners.delete(listener);
  };

  /** Subscribe to per-frame simulated time updates and return an unsubscribe callback. */
  onFrame(listener: (time: number) => void): () => void {
    this.frameListeners.add(listener);
    return () => this.frameListeners.delete(listener);
  }

  /**
   * Set a finite simulation range and reset time to its start.
   *
   * @throws RangeError if the range is nonfinite or reversed.
   */
  setRange(startTime: number, endTime: number): void {
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime < startTime) {
      throw new RangeError(`Invalid simulation range [${startTime}, ${endTime}]`);
    }
    this.startTime = startTime;
    this.endTime = endTime;
    this.currentTime = startTime;
    this.emitFrame();
    this.emitUi();
  }

  /** Start playback, restarting at the beginning if the end was reached. */
  play(): void {
    if (this.isPlaying || this.endTime <= this.startTime) {
      return;
    }
    if (this.currentTime >= this.endTime) {
      this.currentTime = this.startTime;
      this.emitFrame();
    }
    this.isPlaying = true;
    this.lastFrameMs = null;
    this.frameHandle = this.scheduler.request(this.tick);
    this.emitUi();
  }

  /** Pause playback and cancel the scheduled frame. */
  pause(): void {
    if (!this.isPlaying) {
      return;
    }
    this.isPlaying = false;
    this.cancelFrame();
    this.emitUi();
  }

  togglePlay(): void {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  /** Seek to the start without changing playback state. */
  restart(): void {
    this.currentTime = this.startTime;
    this.emitFrame();
    this.emitUi();
  }

  /** Seek to a time clamped to the current range. */
  seek(time: number): void {
    this.currentTime = Math.min(this.endTime, Math.max(this.startTime, time));
    this.emitFrame();
    this.emitUi();
  }

  /**
   * Set playback speed as real seconds per simulated hour.
   *
   * @throws RangeError if the duration is nonfinite or not positive.
   */
  setRealSecondsPerSimHour(realSeconds: number): void {
    if (!Number.isFinite(realSeconds) || realSeconds <= 0) {
      throw new RangeError(`Invalid speed: ${realSeconds}`);
    }
    this.realSecondsPerSimHour = realSeconds;
    this.emitUi();
  }

  /** Advance playback by real milliseconds, capped to prevent background-tab jumps. */
  advance(realDeltaMs: number): void {
    if (!this.isPlaying) {
      return;
    }
    const delta = Math.min(MAX_FRAME_DELTA_MS, Math.max(0, realDeltaMs));
    this.currentTime = Math.min(this.endTime, this.currentTime + (delta / 1000) * this.rate);
    this.emitFrame();
    if (this.currentTime >= this.endTime) {
      this.isPlaying = false;
      this.cancelFrame();
      this.emitUi();
    }
  }

  /** Cancel scheduled work and remove all listeners. */
  dispose(): void {
    this.cancelFrame();
    this.isPlaying = false;
    this.frameListeners.clear();
    this.uiListeners.clear();
  }

  private tick = (timestampMs: number): void => {
    this.frameHandle = null;
    if (!this.isPlaying) {
      return;
    }
    const delta = this.lastFrameMs === null ? 0 : timestampMs - this.lastFrameMs;
    this.lastFrameMs = timestampMs;
    this.advance(delta);
    if (this.isPlaying) {
      if (timestampMs - this.lastUiNotifyMs >= this.uiIntervalMs) {
        this.lastUiNotifyMs = timestampMs;
        this.emitUi();
      }
      this.frameHandle = this.scheduler.request(this.tick);
    }
  };

  private cancelFrame(): void {
    if (this.frameHandle !== null) {
      this.scheduler.cancel(this.frameHandle);
      this.frameHandle = null;
    }
    this.lastFrameMs = null;
  }

  private emitFrame(): void {
    for (const listener of this.frameListeners) {
      listener(this.currentTime);
    }
  }

  private emitUi(): void {
    this.snapshot = this.buildSnapshot();
    for (const listener of this.uiListeners) {
      listener();
    }
  }

  private buildSnapshot(): ClockSnapshot {
    return {
      currentTime: this.currentTime,
      startTime: this.startTime,
      endTime: this.endTime,
      isPlaying: this.isPlaying,
      realSecondsPerSimHour: this.realSecondsPerSimHour,
    };
  }
}
