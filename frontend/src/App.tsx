import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { createDataClients } from "./api";
import arrivalChimeUrl from "./assets/arrival-chime.wav?url";
import { ArrivalChime } from "./audio/arrivalChime";
import { ControlPanel } from "./components/ControlPanel";
import { Legend } from "./components/Legend";
import { DEFAULT_PREFERENCES, IndicatorWeights, toSafetyWeights } from "./components/IndicatorWeights";
import { ScenarioPicker } from "./components/ScenarioPicker";
import { StatusOverlay } from "./components/StatusOverlay";
import { loadConfig } from "./config";
import { populationScale, type Arrival } from "./data/arrivals";
import { useScenarios } from "./data/useScenarios";
import { useTripData } from "./data/useTripData";
import { MapView } from "./map/MapView";
import { SimulationClock } from "./simulation/SimulationClock";
import { DEFAULT_REAL_SECONDS_PER_SIM_HOUR } from "./simulation/speedPresets";

/** Coordinate data sources, scenario selection, simulation and map status. */
export function App() {
  const config = useMemo(() => loadConfig(), []);
  const clients = useMemo(() => createDataClients(config), [config]);
  const clock = useMemo(() => new SimulationClock({ realSecondsPerSimHour: DEFAULT_REAL_SECONDS_PER_SIM_HOUR }), []);
  const chime = useMemo(() => new ArrivalChime(arrivalChimeUrl), []);
  const catalog = useScenarios(clients.scenarios);
  const scenarios = useMemo(() => (catalog.status === "success" ? catalog.scenarios : []), [catalog]);
  const [requestedScenarioId, setRequestedScenarioId] = useState<string | null>(null);
  const selectedScenario =
    scenarios.find((scenario) => scenario.id === requestedScenarioId) ?? scenarios[0] ?? null;
  const selectedScenarioId = selectedScenario?.id ?? null;
  const [mapError, setMapError] = useState<string | null>(null);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const weights = useMemo(() => toSafetyWeights(preferences), [preferences]);
  const data = useTripData(clients, selectedScenarioId, weights);
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

  const handleScenarioSelect = useCallback((scenarioId: string) => setRequestedScenarioId(scenarioId), []);
  const handleArrivals = useCallback(
    (arrivals: Arrival[]) => {
      const largest = Math.max(...arrivals.map((arrival) => arrival.population));
      chime.play(populationScale(largest));
    },
    [chime],
  );
  const simulatedLabel = getSimulatedLabel(clients.tripsSimulated, clients.safetySimulated);

  return (
    <main className="relative h-full w-full overflow-hidden bg-night text-ink">
      <MapView
        dataset={dataset}
        clock={clock}
        scenarios={scenarios}
        selectedScenarioId={selectedScenarioId}
        onScenarioSelect={handleScenarioSelect}
        onArrivals={handleArrivals}
        onMapError={setMapError}
      />

      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3 pb-8 sm:p-4 sm:pb-8">
        <header className="flex items-start justify-between gap-3">
          <div className="pointer-events-auto max-w-sm rounded-xl border border-surface-raised/70 bg-surface/80 px-3 py-2 shadow-xl shadow-night/60 backdrop-blur-md">
            <h1 className="text-sm font-semibold tracking-wide">
              Noctambulle <span className="text-trip">·</span> Île-de-France
            </h1>
            <p className="mt-0.5 text-xs text-ink-muted">
              {simulatedLabel && (
                <span className="mr-1.5 rounded border border-highlight/60 px-1 py-px text-[10px] font-semibold tracking-wide text-highlight uppercase">
                  {simulatedLabel}
                </span>
              )}
              Cliquez sur un point de départ pour afficher son scénario.
            </p>
            {selectedScenario && (
              <ScenarioPicker
                scenarios={scenarios}
                selected={selectedScenario}
                onSelect={handleScenarioSelect}
              />
            )}
          </div>
          <div className="pointer-events-auto mr-11 flex max-h-[calc(100vh-19rem)] flex-col gap-2 overflow-y-auto">
            <IndicatorWeights preferences={preferences} onChange={setPreferences} />
            <Legend safetySimulated={clients.safetySimulated} />
          </div>
        </header>

        <div className="flex flex-col items-center gap-2">
          {mapError && <Notice>{mapError}</Notice>}
          {data.status === "success" && data.safetyError && (
            <Notice>
              Indicateurs indisponibles : les trajets et leurs scores sont affichés en « non disponible ».
            </Notice>
          )}
          <ControlPanel clock={clock} dataset={dataset} chime={chime} />
        </div>
      </div>

      {catalog.status === "loading" && <StatusOverlay kind="loading" title="Chargement des scénarios…" />}
      {catalog.status === "error" && (
        <StatusOverlay kind="error" title="Les scénarios n'ont pas pu être chargés." onRetry={catalog.reload}>
          {catalog.message}
        </StatusOverlay>
      )}
      {catalog.status === "success" && scenarios.length === 0 && (
        <StatusOverlay kind="empty" title="Aucun scénario disponible.">
          Aucun fichier de scénario n'a été trouvé par le service routing.
        </StatusOverlay>
      )}
      {data.status === "loading" && <StatusOverlay kind="loading" title="Chargement des trajets…" />}
      {data.status === "error" && (
        <StatusOverlay kind="error" title="Les trajets n'ont pas pu être chargés." onRetry={data.reload}>
          {data.message}
        </StatusOverlay>
      )}
      {data.status === "success" && data.dataset.trips.length === 0 && (
        <StatusOverlay kind="empty" title="Aucun trajet pour ce scénario.">
          Choisissez un autre point de départ sur la carte.
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
