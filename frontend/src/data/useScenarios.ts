import { useCallback, useEffect, useState } from "react";
import type { ScenariosClient } from "../api/clients";
import type { ScenarioSummary } from "../domain/types";
import { describeError } from "./useTripData";

export type ScenarioListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; scenarios: ScenarioSummary[] };

/** Charge le catalogue des scenarios (points de depart affiches sur la carte). */
export function useScenarios(client: ScenariosClient): ScenarioListState & { reload: () => void } {
  const [state, setState] = useState<ScenarioListState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    client
      .listScenarios(controller.signal)
      .then((scenarios) => {
        if (!controller.signal.aborted) setState({ status: "success", scenarios });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        console.error("Routing service failed", error);
        setState({ status: "error", message: describeError(error) });
      });
    return () => controller.abort();
  }, [client, attempt]);

  return { ...state, reload };
}
