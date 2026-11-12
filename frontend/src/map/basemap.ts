import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { palette } from "../theme/palette";

/** CARTO dark vector basemap using OpenStreetMap data, without an API key. */
export const BASEMAP_STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

/** Initial view centered on Île-de-France. */
export const INITIAL_VIEW = {
  center: [2.42, 48.84] as [number, number],
  zoom: 9.2,
  minZoom: 7,
  maxZoom: 17,
};

/** Minimal style used when the remote basemap cannot be loaded. */
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
    // Leave layers unchanged when the style does not support a paint property.
  }
}

/** Recolor supported CARTO layers using the project's night palette. */
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
