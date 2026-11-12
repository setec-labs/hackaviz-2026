import type { PickingInfo } from "@deck.gl/core";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { Map as MapLibreMap, NavigationControl, setWorkerUrl, type IControl } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { Arrival } from "../data/arrivals";
import type { RenderDataset } from "../data/prepareDataset";
import type { ScenarioSummary } from "../domain/types";
import { ArrivalTracker } from "../layers/arrivalTracker";
import { buildLayers, LAYER_IDS } from "../layers/buildLayers";
import { HeadBuffers } from "../layers/headPositions";
import { buildTooltip } from "../layers/tooltip";
import type { SimulationClock } from "../simulation/SimulationClock";
import { applyNightPalette, BASEMAP_STYLE_URL, FALLBACK_STYLE, INITIAL_VIEW } from "./basemap";

// MapLibre resout son worker relativement a son propre module, ce que le pre-bundling Vite casse.
setWorkerUrl(maplibreWorkerUrl);

interface MapViewProps {
  dataset: RenderDataset | null;
  clock: SimulationClock;
  scenarios: ScenarioSummary[];
  selectedScenarioId: string | null;
  onScenarioSelect: (scenarioId: string) => void;
  /** Appele lorsque de nouvelles bulles d'arrivee apparaissent pendant la lecture. */
  onArrivals?: (arrivals: Arrival[]) => void;
  onMapError: (message: string) => void;
}

/**
 * Carte MapLibre + overlay deck.gl. Le rendu des couches est pilote directement par
 * l'horloge (`clock.onFrame`) : aucun rendu React n'a lieu pendant l'animation.
 */
export function MapView({
  dataset,
  clock,
  scenarios,
  selectedScenarioId,
  onScenarioSelect,
  onArrivals,
  onMapError,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const datasetRef = useRef<RenderDataset | null>(dataset);
  const headsRef = useRef<HeadBuffers | null>(null);
  const selectedRef = useRef<string | null>(selectedScenarioId);
  selectedRef.current = selectedScenarioId;
  const callbacksRef = useRef({ onScenarioSelect, onArrivals, onMapError });
  callbacksRef.current = { onScenarioSelect, onArrivals, onMapError };

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
    const isScenario = (info: PickingInfo) => info.layer?.id === LAYER_IDS.scenarios && Boolean(info.object);
    const overlay = new MapboxOverlay({
      interleaved: false,
      layers: [],
      getTooltip: (info) => buildTooltip(info, datasetRef.current, headsRef.current, selectedRef.current),
      onHover: (info) => {
        map.getCanvas().style.cursor = isScenario(info) ? "pointer" : "";
      },
      onClick: (info) => {
        if (isScenario(info)) {
          callbacksRef.current.onScenarioSelect((info.object as ScenarioSummary).id);
        }
      },
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
    const heads = dataset ? new HeadBuffers(dataset.trips.length) : null;
    headsRef.current = heads;
    const arrivals = dataset
      ? new ArrivalTracker(dataset.arrivals, (fresh) => callbacksRef.current.onArrivals?.(fresh))
      : null;
    // Les bulles deja atteintes a l'ouverture du scenario s'affichent sans flash ni son.
    arrivals?.sync(clock.time);
    const render = (time: number) => {
      const nowMs = performance.now();
      arrivals?.update(time, nowMs);
      overlay.setProps({
        layers: buildLayers({ dataset, heads, time, scenarios, selectedScenarioId, arrivals, nowMs }),
      });
    };
    render(clock.time);
    return dataset ? clock.onFrame(render) : undefined;
  }, [dataset, clock, scenarios, selectedScenarioId]);

  return (
    <div className="absolute inset-0">
      <div
        ref={containerRef}
        className="h-full w-full"
        role="region"
        aria-label="Carte des trajets de nuit en Île-de-France. Cliquez sur un point de départ pour afficher son scénario."
      />
    </div>
  );
}
