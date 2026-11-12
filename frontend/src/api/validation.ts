import type { GeoPoint, SafetyIndexValue, ScenarioSummary, Trip } from "../domain/types";

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

function readRecord(value: unknown, where: string): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new ContractError(`${where}: expected an object`);
  }
  return value;
}

function readString(value: unknown, where: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ContractError(`${where}: expected a non-empty string`);
  }
  return value;
}

function readLatitude(value: unknown, where: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < -90 || value > 90) {
    throw new ContractError(`${where}: invalid latitude`);
  }
  return value;
}

function readLongitude(value: unknown, where: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < -180 || value > 180) {
    throw new ContractError(`${where}: invalid longitude`);
  }
  return value;
}

function readGeoPoint(value: unknown, where: string): GeoPoint {
  const source = readRecord(value, where);
  return {
    latitude: readLatitude(source.latitude, `${where}.latitude`),
    longitude: readLongitude(source.longitude, `${where}.longitude`),
  };
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

/**
 * Mode affiche pour un trajet multimodal : "transit" s'il emprunte un transport en commun,
 * "walk" s'il n'est compose que de marche et d'attente, sinon le premier mode fourni.
 */
export function summarizeJourneyMode(legModes: string[]): string | null {
  if (legModes.includes("transit")) return "transit";
  const moving = legModes.filter((mode) => mode !== "wait");
  if (moving.length > 0 && moving.every((mode) => mode.startsWith("walk"))) return "walk";
  return moving[0] ?? null;
}

function parseJourney(raw: unknown, where: string): Trip {
  const journey = readRecord(raw, where);
  const id = readString(journey.journey_id, `${where}.journey_id`);
  const destination = readRecord(journey.destination, `${where}.destination`);
  const destinationName = typeof destination.name === "string" && destination.name.trim() ? destination.name : null;
  const startTimeMs = readTimestamp(journey.start_time, `${where}.start_time`);
  const endTimeMs = readTimestamp(journey.end_time, `${where}.end_time`);
  if (endTimeMs < startTimeMs) {
    throw new ContractError(`${where}: end_time is before start_time`);
  }
  if (!Array.isArray(journey.legs) || journey.legs.length === 0) {
    throw new ContractError(`${where}: at least one leg is required`);
  }
  const { coordinates, offsets_s: offsets } = journey;
  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    throw new ContractError(`${where}: at least two coordinates are required`);
  }
  const legModes: string[] = [];
  const pointModes: string[] = [];
  journey.legs.forEach((rawLeg: unknown, index) => {
    const legWhere = `${where}.legs[${index}]`;
    const leg = readRecord(rawLeg, legWhere);
    const mode = readString(leg.mode, `${legWhere}.mode`);
    const range = leg.point_range;
    // point_range est un intervalle semi-ouvert [debut, fin) ; les troncons partitionnent les positions.
    if (
      !Array.isArray(range) || range.length !== 2 || range[0] !== pointModes.length ||
      !Number.isInteger(range[1]) || range[1] <= range[0] || range[1] > coordinates.length
    ) {
      throw new ContractError(`${legWhere}.point_range: legs must partition the coordinates in order`);
    }
    legModes.push(mode);
    for (let point = range[0]; point < range[1]; point += 1) pointModes.push(mode);
  });
  if (pointModes.length !== coordinates.length) {
    throw new ContractError(`${where}: legs must cover every coordinate`);
  }
  if (!Array.isArray(offsets) || offsets.length !== coordinates.length) {
    throw new ContractError(`${where}: offsets_s must have one value per coordinate`);
  }

  const path: [number, number][] = [];
  const timestampsMs: number[] = [];
  coordinates.forEach((coordinate: unknown, index) => {
    const pointWhere = `${where}.coordinates[${index}]`;
    if (!Array.isArray(coordinate) || coordinate.length !== 2) {
      throw new ContractError(`${pointWhere}: expected [longitude, latitude]`);
    }
    path.push([readLongitude(coordinate[0], pointWhere), readLatitude(coordinate[1], pointWhere)]);
    const offset: unknown = offsets[index];
    if (typeof offset !== "number" || !Number.isFinite(offset) || offset < 0) {
      throw new ContractError(`${where}.offsets_s[${index}]: expected a finite number >= 0`);
    }
    const timestamp = startTimeMs + offset * 1000;
    const previous = timestampsMs[timestampsMs.length - 1];
    if (previous !== undefined && timestamp < previous) {
      throw new ContractError(`${where}.offsets_s[${index}]: offsets must be non-decreasing`);
    }
    timestampsMs.push(timestamp);
  });

  return {
    id,
    destinationName,
    destinationPopulation: readPopulation(destination.population, `${where}.destination.population`),
    mode: summarizeJourneyMode(legModes),
    pointModes,
    startTimeMs,
    endTimeMs,
    path,
    timestampsMs,
  };
}

function readPopulation(value: unknown, where: string): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new ContractError(`${where}: expected an integer >= 0 or null`);
  }
  return value;
}

function parseScenarioSummary(raw: unknown, where: string): ScenarioSummary {
  const scenario = readRecord(raw, where);
  if (typeof scenario.metadata_generated !== "boolean") {
    throw new ContractError(`${where}.metadata_generated: expected a boolean`);
  }
  const journeyCount = scenario.journey_count;
  if (typeof journeyCount !== "number" || !Number.isInteger(journeyCount) || journeyCount < 0) {
    throw new ContractError(`${where}.journey_count: expected an integer >= 0`);
  }
  return {
    id: readString(scenario.id, `${where}.id`),
    name: readString(scenario.name, `${where}.name`),
    description: readString(scenario.description, `${where}.description`),
    metadataGenerated: scenario.metadata_generated,
    origin: readGeoPoint(scenario.origin, `${where}.origin`),
    departureTimeMs: readTimestamp(scenario.departure_time, `${where}.departure_time`),
    journeyCount,
  };
}

/** Valide la reponse de `GET /scenarios`. */
export function parseScenarioListResponse(raw: unknown): ScenarioSummary[] {
  if (!Array.isArray(raw)) {
    throw new ContractError("Scenarios response: expected an array");
  }
  return raw.map((item: unknown, index) => parseScenarioSummary(item, `scenarios[${index}]`));
}

/** Valide la reponse de `GET /scenarios/{id}` et convertit ses trajets en objets du domaine. */
export function parseScenarioResponse(raw: unknown, expectedId: string): Trip[] {
  const summary = parseScenarioSummary(raw, "scenario");
  if (summary.id !== expectedId) {
    throw new ContractError(`Scenario response: expected id "${expectedId}", received "${summary.id}"`);
  }
  const { journeys } = raw as Record<string, unknown>;
  if (!Array.isArray(journeys) || journeys.length !== summary.journeyCount) {
    throw new ContractError("Scenario response: journeys must be an array of journey_count items");
  }
  return journeys.map((journey: unknown, index) => parseJourney(journey, `journeys[${index}]`));
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
