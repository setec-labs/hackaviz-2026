import type { Layer } from "@deck.gl/core";
import { LineLayer, ScatterplotLayer } from "@deck.gl/layers";
import { countReached, type Arrival, type ConstellationLink } from "../data/arrivals";
import type { RenderDataset } from "../data/prepareDataset";
import { rgba, type Rgba } from "../theme/palette";
import type { ArrivalFlash } from "./arrivalTracker";

export const ARRIVAL_LAYER_IDS = {
  constellation: "arrival-constellation",
  halo: "arrival-halo",
  glow: "arrival-glow",
  core: "arrival-core",
  flash: "arrival-flash",
} as const;

const withAlpha = ([r, g, b]: Rgba, alpha: number): Rgba => [r, g, b, alpha];
const getPosition = (arrival: Arrival) => arrival.position;

/** Preserve the visible prefix reference until its source or count changes. */
class PrefixCache<T> {
  private source: readonly T[] | null = null;
  private count = -1;
  private prefix: T[] = [];

  get(source: readonly T[], count: number): T[] {
    if (source !== this.source || count !== this.count) {
      this.source = source;
      this.count = count;
      this.prefix = source.slice(0, count);
    }
    return this.prefix;
  }
}

const arrivalCache = new PrefixCache<Arrival>();
const linkCache = new PrefixCache<ConstellationLink>();

/** Inputs for arrival layers at one simulation frame. */
export interface ArrivalLayerInputs {
  dataset: RenderDataset;
  time: number;
  arrivedCount: number;
  flashes: ArrivalFlash[];
  /** Real time in milliseconds, used for twinkling and flashes. */
  nowMs: number;
}

/**
 * Build arrival halos, cores, links and expanding flashes for one frame.
 * Bubble size reflects population and color reflects the worst-ten-minute
 * index. Implausible trips use a hollow neutral ring without halo or glow.
 */
export function buildArrivalLayers({ dataset, time, arrivedCount, flashes, nowMs }: ArrivalLayerInputs): Layer[] {
  const arrived = arrivalCache.get(dataset.arrivals, arrivedCount);
  const links = linkCache.get(dataset.constellation, countReached(dataset.constellation, time));
  const twinkle = 0.5 + 0.5 * Math.sin(nowMs / 900);

  return [
    new LineLayer<ConstellationLink>({
      id: ARRIVAL_LAYER_IDS.constellation,
      data: links,
      getSourcePosition: (link) => link.from,
      getTargetPosition: (link) => link.to,
      getColor: rgba("selection", 70),
      widthUnits: "pixels",
      getWidth: 1,
    }),
    new ScatterplotLayer<Arrival>({
      id: ARRIVAL_LAYER_IDS.halo,
      data: arrived,
      getPosition,
      radiusUnits: "pixels",
      getRadius: (arrival) => arrival.radiusPx * 2.6,
      getFillColor: (arrival) => withAlpha(arrival.color, arrival.implausible ? 0 : 26),
      opacity: 0.7 + 0.3 * twinkle,
    }),
    new ScatterplotLayer<Arrival>({
      id: ARRIVAL_LAYER_IDS.glow,
      data: arrived,
      getPosition,
      radiusUnits: "pixels",
      getRadius: (arrival) => arrival.radiusPx * 1.6,
      getFillColor: (arrival) => withAlpha(arrival.color, arrival.implausible ? 0 : 70),
    }),
    new ScatterplotLayer<Arrival>({
      id: ARRIVAL_LAYER_IDS.core,
      data: arrived,
      getPosition,
      radiusUnits: "pixels",
      getRadius: (arrival) => arrival.radiusPx,
      getFillColor: (arrival) => withAlpha(arrival.color, arrival.implausible ? 0 : 190),
      stroked: true,
      getLineColor: (arrival) => (arrival.implausible ? withAlpha(arrival.color, 170) : rgba("text", 210)),
      lineWidthUnits: "pixels",
      getLineWidth: (arrival) => (arrival.implausible ? 1.5 : 1),
      pickable: true,
      autoHighlight: true,
      highlightColor: rgba("selection", 200),
    }),
    new ScatterplotLayer<ArrivalFlash>({
      id: ARRIVAL_LAYER_IDS.flash,
      data: flashes,
      getPosition: (flash) => flash.arrival.position,
      radiusUnits: "pixels",
      getRadius: (flash) => flash.arrival.radiusPx * (1 + 3 * Math.sqrt(flash.progress)),
      filled: false,
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      getLineColor: (flash) => withAlpha(flash.arrival.color, Math.round(230 * (1 - flash.progress))),
      updateTriggers: { getRadius: nowMs, getLineColor: nowMs },
    }),
  ];
}
