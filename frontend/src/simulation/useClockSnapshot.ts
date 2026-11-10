import { useSyncExternalStore } from "react";
import type { ClockSnapshot, SimulationClock } from "./SimulationClock";

/** Etat de l'horloge pour l'interface React (mis a jour a frequence reduite). */
export function useClockSnapshot(clock: SimulationClock): ClockSnapshot {
  return useSyncExternalStore(clock.subscribe, clock.getSnapshot);
}
