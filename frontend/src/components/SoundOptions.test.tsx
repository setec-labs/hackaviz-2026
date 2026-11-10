import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SoundOptions } from "./SoundOptions";

describe("SoundOptions", () => {
  it("keeps sound opt-in with a looping asset and no audio preloading", () => {
    const markup = renderToStaticMarkup(<SoundOptions />);
    expect(markup).toContain('<summary');
    expect(markup).toContain('aria-pressed="false"');
    expect(markup).toContain("Activer l&#x27;ambiance sonore");
    expect(markup).toMatch(/<audio[^>]+src="[^"]+\.wav[^"]*"/);
    expect(markup).toContain('loop="" preload="none"');
    expect(markup).not.toContain("autoPlay");
    expect(markup).not.toContain("<details open");
  });

  it("provides a labelled volume control including mute at zero", () => {
    const markup = renderToStaticMarkup(<SoundOptions />);
    expect(markup).toContain('for="ambient-volume"');
    expect(markup).toContain('id="ambient-volume"');
    expect(markup).toContain('min="0" max="100" step="1"');
    expect(markup).toContain('value="30"');
    expect(markup).toContain('aria-valuetext="30 %"');
  });
});
