import type { SafetyIndexValue } from "./types";
import { palette, rgba, rgbToHex, type Rgba } from "../theme/palette";

/*
 * Correspondance entre l'indice (0..1, 1 = plus favorable) et sa representation.
 * Ces seuils sont un choix de visualisation, pas une classification du danger d'un lieu.
 */

export type SafetyLevelId = "favorable" | "intermediate" | "vigilance" | "high-vigilance" | "unavailable";

export interface SafetyLevel {
  id: SafetyLevelId;
  label: string;
  /** Borne basse incluse de l'intervalle (non pertinent pour "unavailable"). */
  minValue: number;
  /** Representation hexadecimale de la couleur (pour l'interface). */
  color: string;
  /** Rayon en pixels du point de tete : la taille double la couleur comme indice visuel. */
  markerRadiusPx: number;
}

const GRADIENT_STOPS: readonly { at: number; color: Rgba }[] = [
  { at: 0, color: rgba("vigilanceHigh") },
  { at: 0.3, color: rgba("vigilance") },
  { at: 0.75, color: rgba("trip") },
];

function mix(a: Rgba, b: Rgba, t: number): Rgba {
  return [0, 1, 2, 3].map((i) => Math.round((a[i] ?? 0) + ((b[i] ?? 0) - (a[i] ?? 0)) * t)) as Rgba;
}

/** Couleur continue : orange (vigilance elevee) -> ambre (vigilance) -> cyan (favorable). */
export function safetyIndexColor(value: SafetyIndexValue, alpha = 255): Rgba {
  if (value === null) {
    return rgba("textMuted", alpha);
  }
  const clamped = Math.min(1, Math.max(0, value));
  let color = GRADIENT_STOPS[GRADIENT_STOPS.length - 1]?.color ?? rgba("trip");
  for (let i = 1; i < GRADIENT_STOPS.length; i += 1) {
    const from = GRADIENT_STOPS[i - 1];
    const to = GRADIENT_STOPS[i];
    if (from && to && clamped <= to.at) {
      color = mix(from.color, to.color, (clamped - from.at) / (to.at - from.at));
      break;
    }
  }
  return [color[0], color[1], color[2], alpha];
}

export const SAFETY_LEVELS: readonly SafetyLevel[] = [
  { id: "favorable", label: "Contexte favorable", minValue: 0.65, color: palette.trip, markerRadiusPx: 3 },
  {
    id: "intermediate",
    label: "Contexte intermédiaire",
    minValue: 0.45,
    color: rgbToHex(safetyIndexColor(0.55)),
    markerRadiusPx: 3.5,
  },
  { id: "vigilance", label: "Vigilance", minValue: 0.25, color: palette.vigilance, markerRadiusPx: 4.5 },
  { id: "high-vigilance", label: "Vigilance élevée", minValue: 0, color: palette.vigilanceHigh, markerRadiusPx: 5.5 },
];

export const UNAVAILABLE_LEVEL: SafetyLevel = {
  id: "unavailable",
  label: "Indicateur non disponible",
  minValue: Number.NaN,
  color: palette.textMuted,
  markerRadiusPx: 3,
};

export function classifySafetyIndex(value: SafetyIndexValue): SafetyLevel {
  if (value === null || !Number.isFinite(value)) {
    return UNAVAILABLE_LEVEL;
  }
  return SAFETY_LEVELS.find((level) => value >= level.minValue) ?? UNAVAILABLE_LEVEL;
}

export const SAFETY_INDEX_DISCLAIMER =
  "Indice lié au sentiment de sécurité, de 0 à 1. C'est un indicateur : il ne mesure pas objectivement le danger d'un lieu.";
