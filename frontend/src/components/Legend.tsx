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
export function Legend({ safetySimulated }: { safetySimulated: boolean }) {
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
          {safetySimulated
            ? "Indice simulé, sans lien avec des lieux réels."
            : "Indice actuellement calculé à partir de l'éclairage nocturne uniquement."}{" "}
          Il n'est évalué que sur les tronçons à pied et d'attente ; les autres tronçons reçoivent une
          valeur neutre provisoire de 0,5.
        </p>
        <div className="mt-2 flex items-start gap-2 text-[11px] leading-snug text-ink-muted">
          <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center" aria-hidden="true">
            <span className="block h-3 w-3 rounded-full bg-selection/70 shadow-[0_0_8px_3px] shadow-selection/50" />
          </span>
          <span>
            <span className="text-ink">Bulles d'arrivée</span> : taille proportionnelle à la population de la
            zone ; couleur selon l'anxiété des 10 pires minutes du trajet             (indicateur moyen sur les
                        10 minutes les plus défavorables, consécutives ou non).
          </span>
        </div>
        <div className="mt-2 flex items-start gap-2 text-[11px] leading-snug text-ink-muted">
          <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center" aria-hidden="true">
            <span className="block h-3 w-3 rounded-full border-[1.5px] border-neutral" />
          </span>
          <span>
            <span className="text-ink">Trajet de plus de 2 h</span> : jugé peu plausible (un taxi aurait sans
            doute été pris). Tracé gris atténué et bulle creuse, indicateur non évalué.
          </span>
        </div>
        <p className="mt-1 text-[11px] leading-snug text-ink-muted">
          {SAFETY_INDEX_DISCLAIMER} La taille du point de tête augmente avec le niveau de vigilance.
        </p>
      </div>
    </details>
  );
}
