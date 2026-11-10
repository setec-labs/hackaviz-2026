import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { palette } from "../theme/palette";

/** Fond vectoriel sombre CARTO (donnees OpenStreetMap), sans cle d'API. */
export const BASEMAP_STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

/** Vue initiale centree sur l'Ile-de-France. */
export const INITIAL_VIEW = {
  center: [2.42, 48.84] as [number, number],
  zoom: 9.2,
  minZoom: 7,
  maxZoom: 17,
};

/** Style minimal utilise si le fond de carte distant ne peut pas etre charge. */
export const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": palette.background } }],
};

type PaintProperty = Parameters<MapLibreMap["setPaintProperty"]>[1];
type PaintValue = Parameters<MapLibreMap["setPaintProperty"]>[2];

function trySetPaint(map: MapLibreMap, layerId: string, property: PaintProperty, value: PaintValue): void {
  try {
    map.setPaintProperty(layerId, property, value);
  } catch {
    // Certaines couches du style ne supportent pas la propriete : on les laisse telles quelles.
  }
}

/** Reteinte le fond CARTO avec la palette du projet pour garder une identite nocturne coherente. */
export function applyNightPalette(map: MapLibreMap): void {
  for (const layer of map.getStyle().layers ?? []) {
    const id = layer.id.toLowerCase();
    switch (layer.type) {
      case "background":
        trySetPaint(map, layer.id, "background-color", palette.background);
        break;
      case "fill":
        if (id.includes("water")) {
          trySetPaint(map, layer.id, "fill-color", palette.surface);
        } else {
          trySetPaint(map, layer.id, "fill-color", palette.background);
          trySetPaint(map, layer.id, "fill-opacity", 0.6);
        }
        break;
      case "line":
        if (id.includes("water")) {
          trySetPaint(map, layer.id, "line-color", palette.surface);
        } else if (id.includes("boundary") || id.includes("admin")) {
          trySetPaint(map, layer.id, "line-color", palette.surfaceRaised);
        } else {
          trySetPaint(map, layer.id, "line-color", palette.network);
          trySetPaint(map, layer.id, "line-opacity", 0.28);
        }
        break;
      case "symbol":
        trySetPaint(map, layer.id, "text-color", palette.textMuted);
        trySetPaint(map, layer.id, "text-halo-color", palette.background);
        trySetPaint(map, layer.id, "text-opacity", 0.75);
        break;
      default:
        break;
    }
  }
}
