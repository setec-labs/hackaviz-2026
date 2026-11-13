import { isImplausibleTrip } from "../domain/tripPlausibility";
import type { SafetyIndexValue, Trip } from "../domain/types";
import type { JourneySafetyResultDto } from "../api/contracts";

/** Apply the duration threshold to the trip's first and last timestamps. */
export function isImplausible(trip: Trip): boolean {
  const first = trip.timestampsMs[0] ?? 0;
  const last = trip.timestampsMs[trip.timestampsMs.length - 1] ?? first;
  return isImplausibleTrip((last - first) / 1000);
}

/** Align contextual responses with rendering order; never substitute neutral values. */
export function mergeJourneySafety(trips: Trip[], results: JourneySafetyResultDto[]): {
  values: SafetyIndexValue[];
  scores: Map<string, SafetyIndexValue>;
} {
  const byId = new Map(results.map((result) => [result.journey_id, result]));
  const values: SafetyIndexValue[] = [];
  const scores = new Map<string, SafetyIndexValue>();
  for (const trip of trips) {
    const result = isImplausible(trip) ? undefined : byId.get(trip.id);
    values.push(...(result?.values ?? trip.path.map(() => null)));
    scores.set(trip.id, result?.score ?? null);
  }
  return { values, scores };
}
