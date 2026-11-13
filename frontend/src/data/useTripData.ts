import { useCallback, useEffect, useRef, useState } from "react";
import type { DataClients } from "../api/clients";
import type { JourneySafetyResultDto, SafetyWeights } from "../api/contracts";
import type { Trip } from "../domain/types";
import { prepareDataset, type RenderDataset } from "./prepareDataset";
import { isImplausible, mergeJourneySafety } from "./safetySampling";

/** Loading state and prepared data for the selected scenario. */
export type TripDataState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; dataset: RenderDataset; safetyError: string | null };

/** Extract a displayable message from a caught value. */
export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Load the scenario and evaluate each leg in its applicable context.
 *
 * A safety service failure does not hide the trips: all values remain
 * unavailable and the failure is exposed in the success state. Requests are
 * canceled when the selection or client changes.
 */
export function useTripData(
  clients: DataClients,
  scenarioId: string | null,
  weights: SafetyWeights,
): TripDataState & { reload: () => void } {
  const [state, setState] = useState<TripDataState>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  const cached = useRef<{ clients: DataClients; id: string; attempt: number; trips: Trip[] } | null>(null);

  useEffect(() => {
    if (scenarioId === null) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });

    (async () => {
      try {
        const previous = cached.current;
        const trips = previous?.clients === clients && previous.id === scenarioId && previous.attempt === attempt
          ? previous.trips
          : await clients.scenarios.fetchScenarioTrips(scenarioId, controller.signal);
        if (controller.signal.aborted) return;
        cached.current = { clients, id: scenarioId, attempt, trips };
        const plausible = trips.filter((trip) => !isImplausible(trip));
        let results: JourneySafetyResultDto[] = [];
        let safetyError: string | null = null;
        if (plausible.length > 0) {
          try {
            results = await clients.safety.fetchJourneySafety(plausible, weights, controller.signal);
          } catch (error) {
            if (controller.signal.aborted) return;
            safetyError = describeError(error);
            console.error("Safety index service failed", error);
          }
        }
        if (controller.signal.aborted) return;
        const { values, scores } = mergeJourneySafety(trips, results);
        setState({ status: "success", dataset: prepareDataset(trips, values, scores), safetyError });
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Routing service failed", error);
        setState({ status: "error", message: describeError(error) });
      }
    })();

    return () => controller.abort();
  }, [clients, scenarioId, attempt, weights]);

  return { ...state, reload };
}
