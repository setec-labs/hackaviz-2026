import { useId } from "react";
import type { ScenarioSummary } from "../domain/types";

interface ScenarioPickerProps {
  scenarios: ScenarioSummary[];
  selected: ScenarioSummary;
  onSelect: (scenarioId: string) => void;
}

/** Provide a keyboard-accessible alternative to selecting map origins. */
export function ScenarioPicker({ scenarios, selected, onSelect }: ScenarioPickerProps) {
  const selectId = useId();
  return (
    <div className="mt-2 border-t border-surface-raised/70 pt-2">
      <label htmlFor={selectId} className="text-[10px] font-semibold tracking-wide text-ink-muted uppercase">
        Scénario
      </label>
      <select
        id={selectId}
        value={selected.id}
        onChange={(event) => onSelect(event.target.value)}
        className="mt-0.5 block w-full rounded-md border border-surface-raised bg-night/60 px-2 py-1 text-xs text-ink focus-visible:outline-2 focus-visible:outline-selection"
      >
        {scenarios.map((scenario) => (
          <option key={scenario.id} value={scenario.id}>
            {scenario.name}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-ink">{selected.description}</p>
      {selected.metadataGenerated && (
        <p className="mt-0.5 text-[11px] text-ink-muted italic">
          Description générée automatiquement à partir des données.
        </p>
      )}
    </div>
  );
}
