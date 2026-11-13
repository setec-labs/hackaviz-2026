/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATA_SOURCE?: string;
  readonly VITE_SAFETY_SOURCE?: string;
  readonly VITE_TRIPS_API_URL?: string;
  readonly VITE_SAFETY_API_URL?: string;
  readonly VITE_MOCK_TRIP_COUNT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
