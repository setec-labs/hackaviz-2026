/** Playback speed label and its real-time duration per simulated hour. */
export interface SpeedPreset {
  label: string;
  /** Real seconds per simulated hour. */
  realSecondsPerSimHour: number;
}

export const SPEED_PRESETS: readonly SpeedPreset[] = [
  { label: "Temps réel", realSecondsPerSimHour: 3600 },
  { label: "Normale", realSecondsPerSimHour: 60 },
  { label: "Rapide", realSecondsPerSimHour: 10 },
  { label: "Très rapide", realSecondsPerSimHour: 1 },
];

export const DEFAULT_REAL_SECONDS_PER_SIM_HOUR = 60;
