import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, IndicatorWeights, toSafetyWeights } from "./IndicatorWeights";

describe("indicator importance", () => {
  it("normalizes every combination and makes higher importance count more", () => {
    for (const lighting of [1, 2, 3] as const) {
      for (const ridership of [1, 2, 3] as const) {
        const weights = toSafetyWeights({ lighting, ridership });
        expect(weights.lighting + weights.ridership).toBe(1);
        expect(weights.lighting).toBeCloseTo(lighting / (lighting + ridership));
      }
    }
    expect(toSafetyWeights({ lighting: 1, ridership: 3 })).toEqual({ lighting: 0.25, ridership: 0.75 });
  });

  it("pairs the colored choices with labels and native keyboard-accessible radio groups", () => {
    const markup = renderToStaticMarkup(
      <IndicatorWeights preferences={DEFAULT_PREFERENCES} onChange={() => undefined} />,
    );
    expect(markup.match(/type="radio"/g)).toHaveLength(6);
    expect(markup.match(/checked=""/g)).toHaveLength(2);
    expect(markup).toContain('name="importance-lighting"');
    expect(markup).toContain('name="importance-ridership"');
    expect(markup).toContain('aria-label="Éclairage : importance faible"');
    expect(markup).toContain('aria-label="Fréquentation : importance forte"');
    expect(markup).toContain("Somme des poids : 100 %");
  });
});
