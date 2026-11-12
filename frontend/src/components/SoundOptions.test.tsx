import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SoundOptions } from "./SoundOptions";
import { readFileSync } from "node:fs";

describe("SoundOptions", () => {
  it("provides a looping asset and sound controls", () => {
    const markup = renderToStaticMarkup(<SoundOptions />);
    expect(markup).toContain('<summary');
    expect(markup).toContain('aria-pressed="false"');
    expect(markup).toContain("Activer l&#x27;ambiance sonore");
    expect(markup).toMatch(/<audio[^>]+src="[^"]+\.wav[^"]*"/);
    expect(markup).toContain('loop="" preload="auto"');
    expect(markup).not.toContain("<details open");
  });

  it("provides a labelled volume control including mute at zero", () => {
    const markup = renderToStaticMarkup(<SoundOptions />);
    expect(markup).toContain('for="ambient-volume"');
    expect(markup).toContain('id="ambient-volume"');
    expect(markup).toContain('min="0" max="100" step="1"');
    expect(markup).toContain('value="50"');
    expect(markup).toContain('aria-valuetext="50 %"');
  });

  it("loops an audio asset trimmed to exactly 41 seconds of PCM samples", () => {
    const wav = readFileSync(new URL("../assets/ambient-loop.wav", import.meta.url));
    expect(wav.toString("ascii", 0, 4)).toBe("RIFF");
    expect(wav.readUInt32LE(4)).toBe(wav.length - 8);
    let byteRate = 0;
    let dataSize = 0;
    for (let offset = 12; offset + 8 <= wav.length;) {
      const id = wav.toString("ascii", offset, offset + 4);
      const size = wav.readUInt32LE(offset + 4);
      if (id === "fmt ") {
        expect(wav.readUInt16LE(offset + 8)).toBe(1);
        byteRate = wav.readUInt32LE(offset + 16);
      }
      if (id === "data") dataSize = size;
      offset += 8 + size + size % 2;
    }
    expect(byteRate).toBeGreaterThan(0);
    expect(dataSize / byteRate).toBe(41);
  });
});
