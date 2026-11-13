import type { SafetyWeights } from "../api/contracts";
import { palette } from "../theme/palette";

export type IndicatorImportance = 1 | 2 | 3;
export interface IndicatorPreferences {
  lighting: IndicatorImportance;
  ridership: IndicatorImportance;
  population_density: IndicatorImportance;
}

export const DEFAULT_PREFERENCES: IndicatorPreferences = {
  lighting: 2, ridership: 2, population_density: 2,
};

/** Translate importance choices to relative weights; keep their sum equal to one. */
export function toSafetyWeights(preferences: IndicatorPreferences): SafetyWeights {
  const total = preferences.lighting + preferences.ridership + preferences.population_density;
  const lighting = preferences.lighting / total;
  const ridership = preferences.ridership / total;
  return { lighting, ridership, population_density: 1 - (lighting + ridership) };
}

const choices = [
  { value: 1, label: "Faible", color: palette.importanceLow },
  { value: 2, label: "Normale", color: palette.neutral },
  { value: 3, label: "Forte", color: palette.importanceHigh },
] as const;

/** Compact, keyboard-accessible choices; colors express importance, not danger. */
export function IndicatorWeights({
  preferences,
  onChange,
}: {
  preferences: IndicatorPreferences;
  onChange: (preferences: IndicatorPreferences) => void;
}) {
  const weights = toSafetyWeights(preferences);
  return (
    <details open className="pointer-events-auto w-72 max-w-[calc(100vw-4rem)] shrink-0 rounded-xl border border-surface-raised/70 bg-surface/90 text-xs shadow-xl">
      <summary className="cursor-pointer rounded-xl px-3 py-2 font-semibold focus-visible:outline-2 focus-visible:outline-selection">
        Pondération du trajet
      </summary>
      <div className="space-y-2 px-3 pb-3">
        {([
          ["lighting", "Éclairage"],
          ["ridership", "Fréquentation"],
          ["population_density", "Densité de population"],
        ] as const).map(([id, label]) => (
          <fieldset key={id} className="flex items-center justify-between gap-2">
            <legend className="float-left">
              {label} <span className="text-ink-muted">({Math.round(weights[id] * 100)} %)</span>
            </legend>
            <div className="flex gap-2">
              {choices.map((choice) => (
                <label key={choice.value} className="flex cursor-pointer flex-col items-center gap-1 text-[10px]">
                  <input
                    type="radio"
                    name={`importance-${id}`}
                    value={choice.value}
                    checked={preferences[id] === choice.value}
                    onChange={() => onChange({ ...preferences, [id]: choice.value })}
                    className="peer sr-only"
                    aria-label={`${label} : importance ${choice.label.toLowerCase()}`}
                  />
                  <span
                    aria-hidden="true"
                    style={{ backgroundColor: choice.color }}
                    className="h-4 w-4 rounded-full border border-ink-muted peer-checked:ring-2 peer-checked:ring-selection peer-checked:ring-offset-2 peer-checked:ring-offset-surface peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-selection"
                  />
                  <span>{choice.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <p className="text-[11px] leading-snug text-ink-muted">
          Rouge = faible, gris = normale, vert = forte. Somme des poids : 100 %
          (pourcentages affichés arrondis).
          Les couleurs locales ne changent pas ; les bulles résument le score pondéré.
        </p>
      </div>
    </details>
  );
}
