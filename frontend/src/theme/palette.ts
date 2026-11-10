/**
 * Palette du projet (voir frontend/AGENTS.md).
 * Source unique pour le code TypeScript (deck.gl, MapLibre). Les memes valeurs sont
 * exposees a Tailwind dans `src/index.css` (bloc `@theme`) : garder les deux synchronises.
 */
export const palette = {
  background: "#061B3A",
  surface: "#0B2F5B",
  surfaceRaised: "#164878",
  network: "#286FAE",
  trip: "#35C5F4",
  selection: "#8DE5FA",
  text: "#F3F8FC",
  textMuted: "#A9C4DD",
  highlight: "#FFE08A",
  vigilance: "#FFBF47",
  vigilanceHigh: "#FF7A45",
} as const;

export type PaletteColor = keyof typeof palette;

export type Rgb = [number, number, number];
export type Rgba = [number, number, number, number];

export function hexToRgb(hex: string): Rgb {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match?.[1]) {
    throw new Error(`Invalid hex color: ${hex}`);
  }
  const value = Number.parseInt(match[1], 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

export function rgba(color: PaletteColor, alpha = 255): Rgba {
  const [r, g, b] = hexToRgb(palette[color]);
  return [r, g, b, alpha];
}

export function rgbToHex([r, g, b]: Rgb | Rgba): string {
  return `#${[r, g, b].map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
}
