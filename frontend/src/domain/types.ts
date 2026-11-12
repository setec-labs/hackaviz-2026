/** Domain types used by the application, independent of API wire formats. */

/** WGS84 geographic position in degrees. */
export interface GeoPoint {
  latitude: number;
  longitude: number;
}

/** Scenario with one origin and departure time and multiple destinations. */
export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  /** Whether missing name or description was generated from scenario data. */
  metadataGenerated: boolean;
  origin: GeoPoint;
  departureTimeMs: number;
  journeyCount: number;
}

/** Domain journey with aligned path, timestamps and per-point modes. */
export interface Trip {
  id: string;
  /** Destination name, or null if absent. */
  destinationName: string | null;
  /** Destination population, or null if absent. */
  destinationPopulation: number | null;
  /** Summarized travel mode, or null if absent. */
  mode: string | null;
  /** Mode of the leg containing each position, such as `walk_access`, `wait`, or `transit`. */
  pointModes: string[];
  /** Start and end times in UTC epoch milliseconds. */
  startTimeMs: number;
  endTimeMs: number;
  /** Ordered deck.gl positions as [longitude, latitude]. */
  path: [number, number][];
  /** Nondecreasing UTC epoch timestamp in milliseconds for each position. */
  timestampsMs: number[];
}

/**
 * Normalized contextual index in [0, 1], where 1 is most favorable.
 * `null` means unavailable. This indicator is not an objective measure of danger.
 */
export type SafetyIndexValue = number | null;
