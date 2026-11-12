/** Minimum interval between chimes to avoid saturation during grouped arrivals. */
const MIN_INTERVAL_MS = 120;

/**
 * Play arrival chimes with Web Audio, respecting browser autoplay restrictions.
 * Multiple voices may overlap, but starts are rate-limited.
 */
export class ArrivalChime {
  enabled = true;
  /** Playback volume, normally between 0 and 1. */
  volume = 0.5;
  private context: AudioContext | null = null;
  private buffer: Promise<AudioBuffer | null> | null = null;
  private lastPlayMs = Number.NEGATIVE_INFINITY;

  constructor(private readonly url: string) {}

  /** Play with a clamped pitch scale: 0 is higher, 1 is lower. */
  play(pitch = 0.5, nowMs = performance.now()): void {
    if (!this.enabled || this.volume <= 0 || nowMs - this.lastPlayMs < MIN_INTERVAL_MS) return;
    this.lastPlayMs = nowMs;
    void this.start(1.2 - 0.35 * Math.min(1, Math.max(0, pitch)));
  }

  private async start(playbackRate: number): Promise<void> {
    try {
      if (typeof AudioContext === "undefined") return;
      const context = (this.context ??= new AudioContext());
      this.buffer ??= fetch(this.url)
        .then((response) => response.arrayBuffer())
        .then((data) => context.decodeAudioData(data))
        .catch((error: unknown) => {
          console.warn("Arrival chime unavailable", error);
          return null;
        });
      if (context.state === "suspended") void context.resume().catch(() => {});
      const buffer = await this.buffer;
      if (!buffer || context.state !== "running") return;
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.playbackRate.value = playbackRate;
      const gain = context.createGain();
      gain.gain.value = this.volume * 0.8;
      source.connect(gain).connect(context.destination);
      source.start();
    } catch (error) {
      console.warn("Arrival chime failed", error);
    }
  }
}
