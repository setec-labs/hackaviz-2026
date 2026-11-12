import { useSyncExternalStore } from "react";
import type { ClockSnapshot, SimulationClock } from "./SimulationClock";

/** Subscribe React to the clock's throttled UI snapshots. */
export function useClockSnapshot(clock: SimulationClock): ClockSnapshot {
  return useSyncExternalStore(clock.subscribe, clock.getSnapshot);
}
