import type { GeoPoint, SafetyIndexValue, Trip } from "../domain/types";

/** Erreur levee lorsqu'une reponse d'API ne respecte pas le contrat attendu. */
export class ContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContractError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readCoordinate(source: Record<string, unknown>, where: string): GeoPoint {
  const { latitude, longitude } = source;
  if (typeof latitude !== "number" || !Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
    throw new ContractError(`${where}: invalid latitude`);
  }
  if (typeof longitude !== "number" || !Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    throw new ContractError(`${where}: invalid longitude`);
  }
  return { latitude, longitude };
}

function readTimestamp(value: unknown, where: string): number {
  if (typeof value !== "string") {
    throw new ContractError(`${where}: timestamp must be an ISO 8601 string`);
  }
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) {
    throw new ContractError(`${where}: invalid timestamp "${value}"`);
  }
  return ms;
}

function parseTrip(raw: unknown, index: number): Trip {
  const where = `trips[${index}]`;
  if (!isRecord(raw)) {
    throw new ContractError(`${where}: expected an object`);
  }
  if (typeof raw.trip_id !== "string" || raw.trip_id.length === 0) {
    throw new ContractError(`${where}: missing trip_id`);
  }
  const startTimeMs = readTimestamp(raw.start_time, `${where}.start_time`);
  const endTimeMs = readTimestamp(raw.end_time, `${where}.end_time`);
  if (endTimeMs < startTimeMs) {
    throw new ContractError(`${where}: end_time is before start_time`);
  }
  if (!Array.isArray(raw.points) || raw.points.length < 2) {
    throw new ContractError(`${where}: at least two points are required`);
  }
  const mode = typeof raw.mode === "string" ? raw.mode : null;

  const path: [number, number][] = [];
  const timestampsMs: number[] = [];
  raw.points.forEach((point: unknown, pointIndex) => {
    const pointWhere = `${where}.points[${pointIndex}]`;
    if (!isRecord(point)) {
      throw new ContractError(`${pointWhere}: expected an object`);
    }
    const { latitude, longitude } = readCoordinate(point, pointWhere);
    const timestamp = readTimestamp(point.timestamp, `${pointWhere}.timestamp`);
    const previous = timestampsMs[timestampsMs.length - 1];
    if (previous !== undefined && timestamp < previous) {
      throw new ContractError(`${pointWhere}: timestamps must be ordered`);
    }
    path.push([longitude, latitude]);
    timestampsMs.push(timestamp);
  });

  return { id: raw.trip_id, mode, startTimeMs, endTimeMs, path, timestampsMs };
}

/** Valide une reponse de l'API trajets et la convertit en objets du domaine. */
export function parseTripsResponse(raw: unknown): Trip[] {
  if (!isRecord(raw) || !Array.isArray(raw.trips)) {
    throw new ContractError("Trips response: expected an object with a `trips` array");
  }
  return raw.trips.map(parseTrip);
}

/** Valide une reponse de l'API indice et retourne les valeurs dans l'ordre des points demandes. */
export function parseSafetyIndexResponse(raw: unknown, expectedLength: number): SafetyIndexValue[] {
  if (!isRecord(raw) || !Array.isArray(raw.indices)) {
    throw new ContractError("Safety response: expected an object with an `indices` array");
  }
  if (raw.indices.length !== expectedLength) {
    throw new ContractError(
      `Safety response: expected ${expectedLength} indices, received ${raw.indices.length}`,
    );
  }
  return raw.indices.map((item: unknown, index) => {
    if (!isRecord(item)) {
      throw new ContractError(`indices[${index}]: expected an object`);
    }
    if (item.value === null || item.value === undefined) {
      return null;
    }
    if (typeof item.value !== "number" || !Number.isFinite(item.value) || item.value < 0 || item.value > 1) {
      throw new ContractError(`indices[${index}]: value must be a number in [0, 1] or null`);
    }
    return item.value;
  });
}
