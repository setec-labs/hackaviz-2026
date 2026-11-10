import type { Layer } from "@deck.gl/core";
import { TripsLayer } from "@deck.gl/geo-layers";
import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { RenderDataset, RenderTrip } from "../data/prepareDataset";
import type { GeoPoint } from "../domain/types";
import { rgba } from "../theme/palette";
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
  origin: "origin",
} as const;

export interface LayerInputs {
  dataset: RenderDataset;
  heads: HeadBuffers;
  time: number;
  origin: GeoPoint;
}

/**
 * Construit les couches pour l'instant `time`. Appelee a chaque image par la boucle de
 * l'horloge : deck.gl compare les props et ne reenvoie au GPU que ce qui a change
 * (essentiellement `currentTime` et les positions de tete).
 */
export function buildLayers({ dataset, heads, time, origin }: LayerInputs): Layer[] {
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
    new ScatterplotLayer<GeoPoint>({
      id: LAYER_IDS.origin,
      data: [origin],
      getPosition: (point) => [point.longitude, point.latitude],
      radiusUnits: "pixels",
      getRadius: 9,
      filled: true,
      getFillColor: rgba("highlight", 70),
      stroked: true,
      getLineColor: rgba("highlight", 255),
      lineWidthUnits: "pixels",
      getLineWidth: 2,
    }),
  ];
}
