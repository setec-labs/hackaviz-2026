import type { Layer } from "@deck.gl/core";
import { TripsLayer } from "@deck.gl/geo-layers";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import type { RenderDataset, RenderTrip } from "../data/prepareDataset";
import type { ScenarioSummary } from "../domain/types";
import { rgba } from "../theme/palette";
import { buildArrivalLayers } from "./arrivalLayers";
import type { ArrivalTracker } from "./arrivalTracker";
import type { HeadBuffers } from "./headPositions";

/** Longueur de la trainee, en secondes simulees. */
const TRAIL_LENGTH_SECONDS = 15 * 60;

const getPath = (trip: RenderTrip) => trip.path;
const getTimestamps = (trip: RenderTrip) => trip.timestamps;
const getVertexColors = (trip: RenderTrip) => trip.colors;

export const LAYER_IDS = {
  routes: "routes",
  tripsHalo: "trips-halo",
  trips: "trips",
  heads: "heads",
  scenarios: "scenarios",
  scenarioLabels: "scenario-labels",
} as const;

export interface LayerInputs {
  /** Null tant que les trajets du scenario selectionne ne sont pas charges. */
  dataset: RenderDataset | null;
  heads: HeadBuffers | null;
  time: number;
  scenarios: ScenarioSummary[];
  selectedScenarioId: string | null;
  /** Suivi des bulles d'arrivee, mis a jour pour `time` par l'appelant. */
  arrivals?: ArrivalTracker | null;
  /** Temps reel en ms (animations independantes de la vitesse de simulation). */
  nowMs?: number;
}

const scenarioPosition = (scenario: ScenarioSummary): [number, number] => [
  scenario.origin.longitude,
  scenario.origin.latitude,
];

/** Points de depart cliquables ; le scenario selectionne est plein et plus grand (pas seulement colore). */
function buildScenarioLayers(scenarios: ScenarioSummary[], selectedScenarioId: string | null): Layer[] {
  const isSelected = (scenario: ScenarioSummary) => scenario.id === selectedScenarioId;
  return [
    new ScatterplotLayer<ScenarioSummary>({
      id: LAYER_IDS.scenarios,
      data: scenarios,
      getPosition: scenarioPosition,
      radiusUnits: "pixels",
      getRadius: (scenario) => (isSelected(scenario) ? 11 : 8),
      filled: true,
      getFillColor: (scenario) => (isSelected(scenario) ? rgba("highlight", 220) : rgba("background", 200)),
      stroked: true,
      getLineColor: rgba("highlight", 255),
      lineWidthUnits: "pixels",
      getLineWidth: (scenario) => (isSelected(scenario) ? 3 : 2),
      pickable: true,
      autoHighlight: true,
      highlightColor: rgba("selection", 160),
      updateTriggers: { getRadius: selectedScenarioId, getFillColor: selectedScenarioId, getLineWidth: selectedScenarioId },
    }),
    new TextLayer<ScenarioSummary>({
      id: LAYER_IDS.scenarioLabels,
      data: scenarios,
      getPosition: scenarioPosition,
      getText: (scenario) => scenario.name,
      characterSet: "auto",
      getSize: 12,
      sizeUnits: "pixels",
      getColor: rgba("text", 235),
      getPixelOffset: [0, 18],
      getTextAnchor: "middle",
      getAlignmentBaseline: "top",
      fontWeight: 600,
      outlineWidth: 3,
      outlineColor: rgba("background", 230),
      fontSettings: { sdf: true },
    }),
  ];
}

/**
 * Construit les couches pour l'instant `time`. Appelee a chaque image par la boucle de
 * l'horloge : deck.gl compare les props et ne reenvoie au GPU que ce qui a change
 * (essentiellement `currentTime` et les positions de tete).
 */
export function buildLayers({
  dataset,
  heads,
  time,
  scenarios,
  selectedScenarioId,
  arrivals = null,
  nowMs = 0,
}: LayerInputs): Layer[] {
  const scenarioLayers = buildScenarioLayers(scenarios, selectedScenarioId);
  if (!dataset || !heads) {
    return scenarioLayers;
  }
  const headCount = heads.update(dataset, time);
  // Attenue le fond des itineraires quand le volume augmente pour garder la lisibilite.
  const routeAlpha = Math.round(Math.min(46, Math.max(10, 12000 / Math.max(1, dataset.trips.length))));

  return [
    new PathLayer<RenderTrip>({
      id: LAYER_IDS.routes,
      data: dataset.trips,
      getPath,
      getColor: rgba("network", routeAlpha),
      widthUnits: "pixels",
      getWidth: 1,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<RenderTrip>({
      id: LAYER_IDS.tripsHalo,
      data: dataset.trips,
      getPath,
      getTimestamps,
      getColor: getVertexColors,
      widthUnits: "pixels",
      getWidth: 8,
      opacity: 0.14,
      capRounded: true,
      jointRounded: true,
      fadeTrail: true,
      trailLength: TRAIL_LENGTH_SECONDS,
      currentTime: time,
    }),
    new TripsLayer<RenderTrip>({
      id: LAYER_IDS.trips,
      data: dataset.trips,
      getPath,
      getTimestamps,
      getColor: getVertexColors,
      widthUnits: "pixels",
      getWidth: 2.5,
      opacity: 0.95,
      capRounded: true,
      jointRounded: true,
      fadeTrail: true,
      trailLength: TRAIL_LENGTH_SECONDS,
      currentTime: time,
      pickable: true,
      autoHighlight: true,
      highlightColor: rgba("selection", 220),
    }),
    ...(arrivals
      ? buildArrivalLayers({
          dataset,
          time,
          arrivedCount: arrivals.arrivedCount,
          flashes: arrivals.activeFlashes(nowMs),
          nowMs,
        })
      : []),
    new ScatterplotLayer({
      id: LAYER_IDS.heads,
      // Des vues `subarray` neuves a chaque image forcent deck.gl a reenvoyer les buffers.
      data: {
        length: headCount,
        attributes: {
          getPosition: { value: heads.positions.subarray(0, headCount * 2), size: 2 },
          getFillColor: { value: heads.colors.subarray(0, headCount * 4), size: 4, normalized: true },
          getRadius: { value: heads.radii.subarray(0, headCount), size: 1 },
        },
      },
      radiusUnits: "pixels",
      stroked: true,
      getLineColor: rgba("background", 230),
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      pickable: true,
      autoHighlight: true,
      highlightColor: rgba("selection", 255),
    }),
    ...scenarioLayers,
  ];
}
