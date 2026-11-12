import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { createDataClients } from "./api";
import { ControlPanel } from "./components/ControlPanel";
import { Legend } from "./components/Legend";
import { StatusOverlay } from "./components/StatusOverlay";
import { loadConfig } from "./config";
import { useTripData } from "./data/useTripData";
import type { GeoPoint } from "./domain/types";
import { MapView } from "./map/MapView";
import { SimulationClock } from "./simulation/SimulationClock";
import { DEFAULT_REAL_SECONDS_PER_SIM_HOUR } from "./simulation/speedPresets";

export function App() {
  const config = useMemo(() => loadConfig(), []);
  const clients = useMemo(() => createDataClients(config), [config]);
  const clock = useMemo(() => new SimulationClock({ realSecondsPerSimHour: DEFAULT_REAL_SECONDS_PER_SIM_HOUR }), []);
  const [origin, setOrigin] = useState<GeoPoint>(config.initialOrigin);
  const [mapError, setMapError] = useState<string | null>(null);
  const data = useTripData(clients, origin);
  const dataset = data.status === "success" ? data.dataset : null;

  useEffect(() => () => clock.pause(), [clock]);

  useEffect(() => {
    if (!dataset) {
      clock.pause();
      return;
    }
    clock.pause();
    clock.setRange(dataset.startTime, dataset.endTime);
    if (dataset.trips.length > 0) {
      clock.play();
    }
  }, [dataset, clock]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.code !== "Space" || target?.closest("button, input, select, textarea, summary, a, [contenteditable]")) return;
      event.preventDefault();
      clock.togglePlay();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [clock]);

  const handleOriginChange = useCallback((point: GeoPoint) => setOrigin(point), []);
  const simulatedLabel = getSimulatedLabel(clients.tripsSimulated, clients.safetySimulated);

  return (
    <main className="relative h-full w-full overflow-hidden bg-night text-ink">
      <MapView
        dataset={dataset}
        clock={clock}
        origin={origin}
        onOriginChange={handleOriginChange}
        onMapError={setMapError}
      />

      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3 pb-8 sm:p-4 sm:pb-8">
        <header className="flex items-start justify-between gap-3">
          <div className="pointer-events-auto rounded-xl border border-surface-raised/70 bg-surface/80 px-3 py-2 shadow-xl shadow-night/60 backdrop-blur-md">
            <h1 className="text-sm font-semibold tracking-wide">
              Trajets de nuit <span className="text-trip">·</span> Île-de-France
            </h1>
            <p className="mt-0.5 text-xs text-ink-muted">
              {simulatedLabel && (
                <span className="mr-1.5 rounded border border-highlight/60 px-1 py-px text-[10px] font-semibold tracking-wide text-highlight uppercase">
                  {simulatedLabel}
                </span>
              )}
              Cliquez sur la carte pour changer le point de départ.
            </p>
          </div>
          <div className="mr-11">
            <Legend safetySimulated={clients.safetySimulated} />
          </div>
        </header>

        <div className="flex flex-col items-center gap-2">
          {mapError && <Notice>{mapError}</Notice>}
          {data.status === "success" && data.safetyError && (
            <Notice>
              Indicateur de sentiment de sécurité indisponible : les trajets sont affichés en « non disponible ».
            </Notice>
          )}
          <ControlPanel clock={clock} dataset={dataset} />
        </div>
      </div>

      {data.status === "loading" && <StatusOverlay kind="loading" title="Chargement des trajets…" />}
      {data.status === "error" && (
        <StatusOverlay kind="error" title="Les trajets n'ont pas pu être chargés." onRetry={data.reload}>
          {data.message}
        </StatusOverlay>
      )}
      {data.status === "success" && data.dataset.trips.length === 0 && (
        <StatusOverlay kind="empty" title="Aucun trajet pour ce point de départ.">
          Cliquez ailleurs sur la carte pour essayer un autre point.
        </StatusOverlay>
      )}
    </main>
  );
}

function getSimulatedLabel(tripsSimulated: boolean, safetySimulated: boolean): string | null {
  if (tripsSimulated && safetySimulated) return "Données simulées";
  if (tripsSimulated) return "Trajets simulés";
  if (safetySimulated) return "Indice simulé";
  return null;
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p
      role="status"
      className="pointer-events-auto flex items-center gap-2 rounded-lg border border-vigilance/70 bg-surface/90 px-3 py-1.5 text-xs text-ink backdrop-blur-md"
    >
      <span aria-hidden="true" className="font-bold text-vigilance">
        !
      </span>
      {children}
    </p>
  );
}
