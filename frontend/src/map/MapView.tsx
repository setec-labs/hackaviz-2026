import { MapboxOverlay } from "@deck.gl/mapbox";
import { Map as MapLibreMap, NavigationControl, setWorkerUrl, type IControl } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { RenderDataset } from "../data/prepareDataset";
import type { GeoPoint } from "../domain/types";
import { buildLayers } from "../layers/buildLayers";
import { HeadBuffers } from "../layers/headPositions";
import { buildTooltip } from "../layers/tooltip";
import type { SimulationClock } from "../simulation/SimulationClock";
import { applyNightPalette, BASEMAP_STYLE_URL, FALLBACK_STYLE, INITIAL_VIEW } from "./basemap";

// MapLibre resout son worker relativement a son propre module, ce que le pre-bundling Vite casse.
setWorkerUrl(maplibreWorkerUrl);

interface MapViewProps {
  dataset: RenderDataset | null;
  clock: SimulationClock;
  origin: GeoPoint;
  onOriginChange: (origin: GeoPoint) => void;
  onMapError: (message: string) => void;
}

/**
 * Carte MapLibre + overlay deck.gl. Le rendu des couches est pilote directement par
 * l'horloge (`clock.onFrame`) : aucun rendu React n'a lieu pendant l'animation.
 */
export function MapView({ dataset, clock, origin, onOriginChange, onMapError }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const datasetRef = useRef<RenderDataset | null>(dataset);
  const headsRef = useRef<HeadBuffers | null>(null);
  const callbacksRef = useRef({ onOriginChange, onMapError });
  callbacksRef.current = { onOriginChange, onMapError };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let map: MapLibreMap;
    try {
      map = new MapLibreMap({
        container,
        style: BASEMAP_STYLE_URL,
        center: INITIAL_VIEW.center,
        zoom: INITIAL_VIEW.zoom,
        minZoom: INITIAL_VIEW.minZoom,
        maxZoom: INITIAL_VIEW.maxZoom,
        attributionControl: { compact: true },
      });
    } catch (error) {
      console.error("Map initialisation failed", error);
      callbacksRef.current.onMapError("La carte n'a pas pu être initialisée (WebGL indisponible ?).");
      return;
    }

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("style.load", () => applyNightPalette(map));

    let styleFailed = false;
    map.on("error", (event) => {
      console.warn("Basemap error", event.error);
      if (!styleFailed && !map.isStyleLoaded()) {
        styleFailed = true;
        map.setStyle(FALLBACK_STYLE);
        callbacksRef.current.onMapError("Fond de carte indisponible : les trajets restent affichés sur un fond uni.");
      }
    });
    map.on("click", (event) => {
      callbacksRef.current.onOriginChange({ latitude: event.lngLat.lat, longitude: event.lngLat.lng });
    });

    const overlay = new MapboxOverlay({
      interleaved: false,
      layers: [],
      getTooltip: (info) => buildTooltip(info, datasetRef.current, headsRef.current),
    });
    map.addControl(overlay as unknown as IControl);
    overlayRef.current = overlay;

    return () => {
      overlayRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    datasetRef.current = dataset;
    const overlay = overlayRef.current;
    if (!overlay) return;
    if (!dataset) {
      headsRef.current = null;
      overlay.setProps({ layers: [] });
      return;
    }
    const heads = new HeadBuffers(dataset.trips.length);
    headsRef.current = heads;
    const render = (time: number) => overlay.setProps({ layers: buildLayers({ dataset, heads, time, origin }) });
    render(clock.time);
    return clock.onFrame(render);
  }, [dataset, clock, origin]);

  return (
    <div className="absolute inset-0">
      <div
        ref={containerRef}
        className="h-full w-full"
        role="region"
        aria-label="Carte des trajets de nuit en Île-de-France. Cliquez pour choisir un nouveau point de départ."
      />
    </div>
  );
}
