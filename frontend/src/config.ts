import type { GeoPoint } from "./domain/types";

export type DataSource = "mock" | "api";
export type MockFailure = "none" | "trips" | "safety";

export interface AppConfig {
  /** Source des trajets. */
  dataSource: DataSource;
  /** Source de l'indice de securite, choisie independamment des trajets. */
  safetySource: DataSource;
  tripsApiUrl: string;
  safetyApiUrl: string;
  initialOrigin: GeoPoint;
  mock: {
    tripCount: number;
    seed: number;
    latencyMs: number;
    failure: MockFailure;
  };
}

export const MAX_MOCK_TRIPS = 20000;
const DEFAULT_MOCK_TRIPS = 250;

/** Chatelet - Les Halles : point de depart par defaut. */
const DEFAULT_ORIGIN: GeoPoint = { latitude: 48.8619, longitude: 2.3466 };

function parseDataSource(value: string | null | undefined, fallback: DataSource): DataSource {
  if (value === "api" || value === "mock") {
    return value;
  }
  if (value !== null && value !== undefined && value.trim() !== "") {
    console.warn(`Ignoring invalid data source "${value}", using ${fallback}`);
  }
  return fallback;
}

function parseInteger(value: string | null | undefined, fallback: number, min: number, max: number): number {
  if (value === null || value === undefined || value.trim() === "") {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    console.warn(`Ignoring invalid numeric setting "${value}", using ${fallback}`);
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

/**
 * Configuration lue depuis les variables Vite (`.env`) et surchargeable par l'URL
 * pour faciliter les tests manuels, par ex. `?trips=3000&seed=7&mockError=safety`.
 * Les trajets sont simules par defaut (`?source=`) ; l'indice de securite vient de
 * l'API safety par defaut (`?safetySource=mock` pour le simuler).
 */
export function loadConfig(search: string = window.location.search): AppConfig {
  const params = new URLSearchParams(search);
  const env = import.meta.env;

  const dataSource = parseDataSource(params.get("source") ?? env.VITE_DATA_SOURCE, "mock");
  const safetySource = parseDataSource(params.get("safetySource") ?? env.VITE_SAFETY_SOURCE, "api");
  const failureParam = params.get("mockError");
  const failure: MockFailure = failureParam === "trips" || failureParam === "safety" ? failureParam : "none";

  return {
    dataSource,
    safetySource,
    tripsApiUrl: env.VITE_TRIPS_API_URL ?? "http://localhost:8001",
    safetyApiUrl: env.VITE_SAFETY_API_URL ?? "http://localhost:8002",
    initialOrigin: DEFAULT_ORIGIN,
    mock: {
      tripCount: parseInteger(
        params.get("trips") ?? env.VITE_MOCK_TRIP_COUNT,
        DEFAULT_MOCK_TRIPS,
        0,
        MAX_MOCK_TRIPS,
      ),
      seed: parseInteger(params.get("seed"), 2026, 0, 2 ** 31 - 1),
      latencyMs: parseInteger(params.get("latency"), 400, 0, 10000),
      failure,
    },
  };
}
