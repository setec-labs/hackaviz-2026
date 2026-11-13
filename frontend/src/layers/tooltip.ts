import type { PickingInfo } from "@deck.gl/core";
import { formatDuration, formatIndex, formatMode, formatSimulatedTime } from "../components/format";
import { ANXIETY_WORST_SECONDS, type Arrival } from "../data/arrivals";
import type { RenderDataset, RenderTrip } from "../data/prepareDataset";
import { classifySafetyIndex } from "../domain/safetyLevels";
import { IMPLAUSIBLE_TRIP_LABEL } from "../domain/tripPlausibility";
import type { ScenarioSummary } from "../domain/types";
import { palette } from "../theme/palette";
import type { HeadBuffers } from "./headPositions";
import { ARRIVAL_LAYER_IDS } from "./arrivalLayers";
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

const mutedLine = (text: string) => `<span style="color:${palette.textMuted}">${escapeHtml(text)}</span>`;

function tripLines(dataset: RenderDataset, trip: RenderTrip): string[] {
  return [
    `<strong>${escapeHtml(trip.destinationName ?? trip.id)}</strong>`,
    `${escapeHtml(formatMode(trip.mode))} · ${formatDuration(trip.endTime - trip.startTime)}`,
    `${formatSimulatedTime(dataset.originMs, trip.startTime)} → ${formatSimulatedTime(dataset.originMs, trip.endTime)}`,
    ...(!trip.implausible && trip.globalSafety !== undefined
      ? [`Score global pondéré : ${formatIndex(trip.globalSafety)}`] : []),
    ...(trip.implausible ? [mutedLine(IMPLAUSIBLE_TRIP_LABEL)] : []),
  ];
}

const departureFormatter = new Intl.DateTimeFormat("fr-FR", {
  timeZone: "Europe/Paris",
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function scenarioLines(scenario: ScenarioSummary, selected: boolean): string[] {
  const muted = (text: string) => `<span style="color:${palette.textMuted}">${escapeHtml(text)}</span>`;
  return [
    `<strong>${escapeHtml(scenario.name)}</strong>`,
    escapeHtml(scenario.description),
    ...(scenario.metadataGenerated ? [muted("Description générée automatiquement à partir des données.")] : []),
    muted(`Départ ${departureFormatter.format(scenario.departureTimeMs)} · ${scenario.journeyCount} trajets`),
    muted(selected ? "Scénario affiché" : "Cliquez pour afficher ce scénario"),
  ];
}

const populationFormatter = new Intl.NumberFormat("fr-FR");

function arrivalLines(dataset: RenderDataset, arrival: Arrival): string[] {
  const header = [
    `<strong>${escapeHtml(arrival.destinationName ?? arrival.id)}</strong>`,
    `Arrivée ${formatSimulatedTime(dataset.originMs, arrival.time)}`,
    `Population : ${populationFormatter.format(arrival.population)} hab.${arrival.populationSimulated ? " (simulée)" : ""}`,
  ];
  if (arrival.implausible) {
    return [...header, mutedLine(`${IMPLAUSIBLE_TRIP_LABEL}. Indicateur non évalué.`)];
  }
  const worst = arrival.worstMinutesSafety;
  const anxiety = worst === null ? null : 1 - worst;
  const windowMinutes = ANXIETY_WORST_SECONDS / 60;
  return [
    ...header,
    ...(arrival.globalSafety !== undefined
      ? [`Score global pondéré : ${formatIndex(arrival.globalSafety)}`] : []),
    `Anxiété des ${windowMinutes} pires minutes du trajet : ${formatIndex(anxiety)}`,
    mutedLine(`Indicateur moyen sur ces ${windowMinutes} minutes : ${formatIndex(worst)} — ${classifySafetyIndex(worst).label}`),
    mutedLine("Indicateur, pas une mesure objective du danger."),
  ];
}

/**
 * Build a deck.gl tooltip for a scenario origin, trip, arrival or current head.
 * Dynamic text is escaped before it is included in the HTML.
 */
export function buildTooltip(
  info: PickingInfo,
  dataset: RenderDataset | null,
  heads: HeadBuffers | null,
  selectedScenarioId: string | null = null,
): { html: string; style: Record<string, string> } | null {
  if (info.index < 0) {
    return null;
  }
  let lines: string[] | null = null;
  if (info.layer?.id === LAYER_IDS.scenarios && info.object) {
    const scenario = info.object as ScenarioSummary;
    lines = scenarioLines(scenario, scenario.id === selectedScenarioId);
  } else if (!dataset) {
    return null;
  } else if (info.layer?.id === ARRIVAL_LAYER_IDS.core && info.object) {
    lines = arrivalLines(dataset, info.object as Arrival);
  } else if (info.layer?.id === LAYER_IDS.trips && info.object) {
    lines = tripLines(dataset, info.object as RenderTrip);
  } else if (info.layer?.id === LAYER_IDS.heads && heads && info.index < heads.count) {
    const trip = dataset.trips[heads.tripIndices[info.index] ?? -1];
    if (trip) {
      const raw = heads.safety[info.index] ?? Number.NaN;
      const value = Number.isNaN(raw) ? null : raw;
      lines = trip.implausible
        ? tripLines(dataset, trip)
        : [
            ...tripLines(dataset, trip),
            `Indicateur : ${formatIndex(value)} — ${classifySafetyIndex(value).label}`,
            mutedLine("Indicateur, pas une mesure objective du danger."),
          ];
    }
  }
  return lines ? { html: lines.join("<br/>"), style: TOOLTIP_STYLE } : null;
}
