import type { Layer } from "@deck.gl/core";
import { TripsLayer } from "@deck.gl/geo-layers";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import type { RenderDataset, RenderTrip } from "../data/prepareDataset";
import type { ScenarioSummary } from "../domain/types";
import { rgba } from "../theme/palette";
import { buildArrivalLayers } from "./arrivalLayers";
import type { ArrivalTracker } from "./arrivalTracker";
import type { HeadBuffers } from "./headPositions";

/** Trail length in simulated seconds. */
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

/** Data and animation state used to construct one map frame. */
export interface LayerInputs {
  /** Null until the selected scenario's trips are loaded. */
  dataset: RenderDataset | null;
  heads: HeadBuffers | null;
  time: number;
  scenarios: ScenarioSummary[];
  selectedScenarioId: string | null;
  /** Arrival tracker, updated to `time` by the caller. */
  arrivals?: ArrivalTracker | null;
  /** Real time in milliseconds for speed-independent animations. */
  nowMs?: number;
}

const scenarioPosition = (scenario: ScenarioSummary): [number, number] => [
  scenario.origin.longitude,
  scenario.origin.latitude,
];

/** Build clickable origins, distinguishing the selection by size and fill as well as color. */
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
 * Build the layers at `time` for the clock's current frame.
 * deck.gl compares properties so unchanged data does not need to be resent.
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
  // Fade background routes as the number of trips grows to preserve legibility.
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
      // New subarray views on each frame make deck.gl refresh the binary buffers.
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
