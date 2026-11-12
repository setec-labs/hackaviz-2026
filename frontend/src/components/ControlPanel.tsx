import { useMemo, type CSSProperties } from "react";
import type { ArrivalChime } from "../audio/arrivalChime";
import { countActiveTrips, type RenderDataset } from "../data/prepareDataset";
import type { SimulationClock } from "../simulation/SimulationClock";
import { SPEED_PRESETS } from "../simulation/speedPresets";
import { useClockSnapshot } from "../simulation/useClockSnapshot";
import { formatSimulatedDate, formatSimulatedTime } from "./format";
import { SoundOptions } from "./SoundOptions";

interface ControlPanelProps {
  clock: SimulationClock;
  dataset: RenderDataset | null;
  chime?: ArrivalChime;
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
      <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
      <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" />
    </svg>
  );
}

function RestartIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
      <path
        d="M12 5a7 7 0 1 1-6.6 4.7M5 4v5h5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const iconButton =
  "flex h-10 w-10 items-center justify-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-selection disabled:cursor-not-allowed disabled:opacity-40";

/** Provide playback, timeline, speed and audio controls for the current dataset. */
export function ControlPanel({ clock, dataset, chime }: ControlPanelProps) {
  const snapshot = useClockSnapshot(clock);
  const hasData = dataset !== null && dataset.trips.length > 0;
  const originMs = dataset?.originMs ?? 0;
  const activeTrips = useMemo(
    () => (dataset ? countActiveTrips(dataset, snapshot.currentTime) : 0),
    [dataset, snapshot.currentTime],
  );
  const duration = Math.max(0, snapshot.endTime - snapshot.startTime);
  const progress = duration > 0 ? (snapshot.currentTime - snapshot.startTime) / duration : 0;

  return (
    <details
      open
      aria-label="Contrôle de la simulation"
      className="pointer-events-auto w-full max-w-3xl rounded-2xl border border-surface-raised/70 bg-surface/85 px-4 py-3 text-ink shadow-2xl shadow-night/60 backdrop-blur-md"
    >
      <summary className="cursor-pointer rounded text-xs text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-selection">
        Contrôleur de simulation
      </summary>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`${iconButton} bg-trip text-night hover:bg-selection`}
            onClick={() => clock.togglePlay()}
            disabled={!hasData}
            aria-label={snapshot.isPlaying ? "Mettre en pause" : "Lancer la simulation"}
            title={snapshot.isPlaying ? "Pause (espace)" : "Lecture (espace)"}
          >
            {snapshot.isPlaying ? <PauseIcon /> : <PlayIcon />}
          </button>
          <button
            type="button"
            className={`${iconButton} border border-surface-raised text-ink hover:border-selection hover:text-selection`}
            onClick={() => clock.restart()}
            disabled={!hasData}
            aria-label="Recommencer"
            title="Recommencer"
          >
            <RestartIcon />
          </button>
        </div>

        <div className="min-w-[7.5rem]" aria-live="off">
          <div className="font-mono text-2xl leading-none tabular-nums tracking-tight">
            {hasData ? formatSimulatedTime(originMs, snapshot.currentTime) : "--:--:--"}
          </div>
          <div className="mt-1 text-xs text-ink-muted">
            {hasData ? `${formatSimulatedDate(originMs, snapshot.currentTime)} · heure simulée` : "Heure simulée"}
          </div>
        </div>

        <div className="ml-auto text-right">
          <div className="font-mono text-lg leading-none tabular-nums">
            {activeTrips}
            <span className="text-ink-muted"> / {dataset?.trips.length ?? 0}</span>
          </div>
          <div className="mt-1 text-xs text-ink-muted">trajets en cours / chargés</div>
        </div>
      </div>

      <div className="mt-3">
        <label htmlFor="timeline" className="sr-only">
          Position dans la timeline
        </label>
        <input
          id="timeline"
          type="range"
          min={snapshot.startTime}
          max={Math.max(snapshot.endTime, snapshot.startTime + 1)}
          step={1}
          value={snapshot.currentTime}
          disabled={!hasData}
          onChange={(event) => clock.seek(Number(event.target.value))}
          className="timeline w-full"
          style={{ "--progress": `${progress * 100}%` } as CSSProperties}
          aria-valuetext={hasData ? formatSimulatedTime(originMs, snapshot.currentTime) : undefined}
        />
        <div className="mt-1 flex justify-between font-mono text-[11px] text-ink-muted tabular-nums">
          <span>{hasData ? formatSimulatedTime(originMs, snapshot.startTime) : ""}</span>
          <span>{hasData ? formatSimulatedTime(originMs, snapshot.endTime) : ""}</span>
        </div>
      </div>

      <fieldset className="mt-2 flex flex-wrap items-center gap-2">
        <legend className="sr-only">Vitesse de simulation</legend>
        <span className="text-xs text-ink-muted" aria-hidden="true">
          Vitesse
        </span>
        {SPEED_PRESETS.map((preset) => {
          const selected = snapshot.realSecondsPerSimHour === preset.realSecondsPerSimHour;
          return (
            <button
              key={preset.realSecondsPerSimHour}
              type="button"
              aria-pressed={selected}
              onClick={() => clock.setRealSecondsPerSimHour(preset.realSecondsPerSimHour)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-selection ${
                selected
                  ? "border-selection bg-selection/15 text-selection"
                  : "border-surface-raised text-ink-muted hover:border-trip hover:text-ink"
              }`}
            >
              {preset.label}
              <span className="ml-1 opacity-75">· 1 h = {preset.realSecondsPerSimHour} s</span>
            </button>
          );
        })}
      </fieldset>
      <SoundOptions chime={chime} />
    </details>
  );
}
