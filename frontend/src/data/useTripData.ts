import { useCallback, useEffect, useState } from "react";
import type { DataClients } from "../api/clients";
import type { SafetyIndexValue } from "../domain/types";
import { prepareDataset, type RenderDataset } from "./prepareDataset";
import { collectPedestrianPoints, mergeSafetyValues } from "./safetySampling";

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
 * Load the selected scenario and evaluate its walking and waiting vertices.
 *
 * A safety service failure does not hide the trips: pedestrian values remain
 * unavailable and the failure is exposed in the success state. Requests are
 * canceled when the selection or client changes.
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
        const points = collectPedestrianPoints(trips);
        let pedestrianValues: SafetyIndexValue[] | null = null;
        let safetyError: string | null = null;
        if (points.length > 0) {
          try {
            pedestrianValues = await clients.safety.fetchSafetyIndices(points, controller.signal);
          } catch (error) {
            if (controller.signal.aborted) return;
            safetyError = describeError(error);
            console.error("Safety index service failed", error);
          }
        } else {
          pedestrianValues = [];
        }
        if (controller.signal.aborted) return;
        const safetyValues = mergeSafetyValues(trips, pedestrianValues);
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
