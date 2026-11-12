import { useCallback, useEffect, useState } from "react";
import type { DataClients } from "../api/clients";
import type { SafetyIndexValue } from "../domain/types";
import { prepareDataset, type RenderDataset } from "./prepareDataset";

export type TripDataState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; dataset: RenderDataset; safetyError: string | null };

export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Charge les trajets du scenario selectionne puis l'indice pour tous leurs sommets.
 * Une panne du service indice n'empeche pas l'affichage des trajets : l'indicateur
 * est alors signale comme non disponible plutot que remplace par une valeur inventee.
 */
export function useTripData(
  clients: DataClients,
  scenarioId: string | null,
): TripDataState & { reload: () => void } {
  const [state, setState] = useState<TripDataState>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    if (scenarioId === null) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });

    (async () => {
      try {
        const trips = await clients.scenarios.fetchScenarioTrips(scenarioId, controller.signal);
        const points = trips.flatMap((trip) => trip.path.map(([longitude, latitude]) => ({ latitude, longitude })));
        let safetyValues: SafetyIndexValue[] | null = null;
        let safetyError: string | null = null;
        if (points.length > 0) {
          try {
            safetyValues = await clients.safety.fetchSafetyIndices(points, controller.signal);
          } catch (error) {
            if (controller.signal.aborted) return;
            safetyError = describeError(error);
            console.error("Safety index service failed", error);
          }
        }
        if (controller.signal.aborted) return;
        setState({ status: "success", dataset: prepareDataset(trips, safetyValues), safetyError });
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Routing service failed", error);
        setState({ status: "error", message: describeError(error) });
      }
    })();

    return () => controller.abort();
  }, [clients, scenarioId, attempt]);

  return { ...state, reload };
}
