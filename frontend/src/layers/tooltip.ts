import type { PickingInfo } from "@deck.gl/core";
import { formatDuration, formatIndex, formatMode, formatSimulatedTime } from "../components/format";
import type { RenderDataset, RenderTrip } from "../data/prepareDataset";
import { classifySafetyIndex } from "../domain/safetyLevels";
import { palette } from "../theme/palette";
import type { HeadBuffers } from "./headPositions";
import { LAYER_IDS } from "./buildLayers";

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);
}

const TOOLTIP_STYLE = {
  backgroundColor: palette.surface,
  color: palette.text,
  border: `1px solid ${palette.surfaceRaised}`,
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "12px",
  lineHeight: "1.45",
  maxWidth: "260px",
};

function tripLines(dataset: RenderDataset, trip: RenderTrip): string[] {
  return [
    `<strong>${escapeHtml(trip.id)}</strong>`,
    `${escapeHtml(formatMode(trip.mode))} · ${formatDuration(trip.endTime - trip.startTime)}`,
    `${formatSimulatedTime(dataset.originMs, trip.startTime)} → ${formatSimulatedTime(dataset.originMs, trip.endTime)}`,
  ];
}

/** Infobulle deck.gl : decrit le trajet et, pour un point courant, l'indicateur associe. */
export function buildTooltip(
  info: PickingInfo,
  dataset: RenderDataset | null,
  heads: HeadBuffers | null,
): { html: string; style: Record<string, string> } | null {
  if (!dataset || info.index < 0) {
    return null;
  }
  let lines: string[] | null = null;
  if (info.layer?.id === LAYER_IDS.trips && info.object) {
    lines = tripLines(dataset, info.object as RenderTrip);
  } else if (info.layer?.id === LAYER_IDS.heads && heads && info.index < heads.count) {
    const trip = dataset.trips[heads.tripIndices[info.index] ?? -1];
    if (trip) {
      const raw = heads.safety[info.index] ?? Number.NaN;
      const value = Number.isNaN(raw) ? null : raw;
      lines = [
        ...tripLines(dataset, trip),
        `Indicateur : ${formatIndex(value)} — ${classifySafetyIndex(value).label}`,
        `<span style="color:${palette.textMuted}">Indicateur, pas une mesure objective du danger.</span>`,
      ];
    }
  }
  return lines ? { html: lines.join("<br/>"), style: TOOLTIP_STYLE } : null;
}
