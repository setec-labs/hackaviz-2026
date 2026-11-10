import { SAFETY_INDEX_DISCLAIMER, SAFETY_LEVELS, UNAVAILABLE_LEVEL, type SafetyLevel } from "../domain/safetyLevels";

function formatBound(value: number): string {
  return value.toFixed(2).replace(".", ",");
}

function rangeLabel(level: SafetyLevel, index: number): string {
  if (level.id === "unavailable") return "pas de donnée";
  const upper = index === 0 ? 1 : (SAFETY_LEVELS[index - 1]?.minValue ?? 1);
  return `${formatBound(level.minValue)} – ${formatBound(upper)}`;
}

/** Legende repliable : chaque couleur est associee a un libelle, une plage et une taille de point. */
export function Legend() {
  const levels = [...SAFETY_LEVELS, UNAVAILABLE_LEVEL];
  const gradient = [...SAFETY_LEVELS]
    .reverse()
    .map((level) => level.color)
    .join(", ");

  return (
    <details
      open
      className="group pointer-events-auto w-64 rounded-xl border border-surface-raised/70 bg-surface/85 text-ink shadow-xl shadow-night/60 backdrop-blur-md"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded-xl px-3 py-2 focus-visible:outline-2 focus-visible:outline-selection">
        <span className="text-xs font-semibold tracking-wide uppercase">Sentiment de sécurité</span>
        <span aria-hidden="true" className="text-ink-muted transition-transform group-open:rotate-180">
          ▾
        </span>
      </summary>
      <div className="px-3 pb-3">
        <div className="h-1.5 rounded-full" aria-hidden="true" style={{ background: `linear-gradient(to right, ${gradient})` }} />
        <ul className="mt-2 space-y-1.5">
          {levels.map((level, index) => (
            <li key={level.id} className="flex items-center gap-2 text-xs">
              <span className="flex h-4 w-4 items-center justify-center" aria-hidden="true">
                <span
                  className="block rounded-full ring-1 ring-night"
                  style={{
                    backgroundColor: level.color,
                    width: `${level.markerRadiusPx * 2}px`,
                    height: `${level.markerRadiusPx * 2}px`,
                  }}
                />
              </span>
              <span className="flex-1">{level.label}</span>
              <span className="font-mono text-[11px] text-ink-muted tabular-nums">{rangeLabel(level, index)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] leading-snug text-ink-muted">
          {SAFETY_INDEX_DISCLAIMER} La taille du point de tête augmente avec le niveau de vigilance.
        </p>
      </div>
    </details>
  );
}
