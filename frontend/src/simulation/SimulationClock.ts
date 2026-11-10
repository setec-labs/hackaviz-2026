/**
 * Horloge de simulation unique partagee par toutes les couches animees.
 *
 * - Le temps simule est exprime en secondes relatives a `startTime`/`endTime` (cf. dataset).
 * - Une seule boucle requestAnimationFrame fait avancer le temps ; aucun timer par trajet.
 * - `onFrame` notifie a chaque image (rendu deck.gl, hors React).
 * - `subscribe` notifie React a frequence reduite pour eviter un rendu par image.
 */

export interface ClockSnapshot {
  currentTime: number;
  startTime: number;
  endTime: number;
  isPlaying: boolean;
  /** Nombre de secondes reelles pour 1 heure simulee. */
  realSecondsPerSimHour: number;
}

export interface FrameScheduler {
  request(callback: (timestampMs: number) => void): number;
  cancel(handle: number): void;
}

export interface SimulationClockOptions {
  realSecondsPerSimHour?: number;
  /** Intervalle minimal (ms reelles) entre deux notifications React pendant la lecture. */
  uiIntervalMs?: number;
  scheduler?: FrameScheduler;
}

/** Evite un saut brutal du temps simule apres un onglet en arriere-plan. */
const MAX_FRAME_DELTA_MS = 250;

const browserScheduler: FrameScheduler = {
  request: (callback) => requestAnimationFrame(callback),
  cancel: (handle) => cancelAnimationFrame(handle),
};

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

  /** Secondes simulees ecoulees par seconde reelle. */
  get rate(): number {
    return 3600 / this.realSecondsPerSimHour;
  }

  get time(): number {
    return this.currentTime;
  }

  getSnapshot = (): ClockSnapshot => this.snapshot;

  subscribe = (listener: () => void): (() => void) => {
    this.uiListeners.add(listener);
    return () => this.uiListeners.delete(listener);
  };

  onFrame(listener: (time: number) => void): () => void {
    this.frameListeners.add(listener);
    return () => this.frameListeners.delete(listener);
  }

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

  restart(): void {
    this.currentTime = this.startTime;
    this.emitFrame();
    this.emitUi();
  }

  seek(time: number): void {
    this.currentTime = Math.min(this.endTime, Math.max(this.startTime, time));
    this.emitFrame();
    this.emitUi();
  }

  setRealSecondsPerSimHour(realSeconds: number): void {
    if (!Number.isFinite(realSeconds) || realSeconds <= 0) {
      throw new RangeError(`Invalid speed: ${realSeconds}`);
    }
    this.realSecondsPerSimHour = realSeconds;
    this.emitUi();
  }

  /** Fait avancer l'horloge d'une duree reelle. Utilise par la boucle et par les tests. */
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
