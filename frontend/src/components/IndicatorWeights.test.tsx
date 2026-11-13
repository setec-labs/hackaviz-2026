import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, IndicatorWeights, toSafetyWeights } from "./IndicatorWeights";

describe("indicator importance", () => {
  it("normalizes every combination and makes higher importance count more", () => {
    for (const lighting of [1, 2, 3] as const) {
      for (const ridership of [1, 2, 3] as const) {
        for (const population_density of [1, 2, 3] as const) {
          const weights = toSafetyWeights({ lighting, ridership, population_density });
          const total = lighting + ridership + population_density;
          expect(weights.lighting + weights.ridership + weights.population_density).toBe(1);
          expect(weights.lighting).toBeCloseTo(lighting / total);
          expect(weights.ridership).toBeCloseTo(ridership / total);
          expect(weights.population_density).toBeCloseTo(population_density / total);
        }
      }
    }
    expect(toSafetyWeights({ lighting: 1, ridership: 1, population_density: 3 })).toEqual({
      lighting: 0.2, ridership: 0.2, population_density: 0.6,
    });
  });

  it("pairs the colored choices with labels and native keyboard-accessible radio groups", () => {
    const markup = renderToStaticMarkup(
      <IndicatorWeights preferences={DEFAULT_PREFERENCES} onChange={() => undefined} />,
    );
    expect(markup.match(/type="radio"/g)).toHaveLength(9);
    expect(markup.match(/checked=""/g)).toHaveLength(3);
    expect(markup).toContain('name="importance-lighting"');
    expect(markup).toContain('name="importance-ridership"');
    expect(markup).toContain('name="importance-population_density"');
    expect(markup).toContain('aria-label="Densité de population : importance forte"');
    expect(markup).toContain('aria-label="Éclairage : importance faible"');
    expect(markup).toContain('aria-label="Fréquentation : importance forte"');
    expect(markup).toContain("Somme des poids : 100 %");
  });
});
