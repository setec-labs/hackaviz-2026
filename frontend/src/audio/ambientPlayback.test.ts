import { afterEach, describe, expect, it, vi } from "vitest";
import { startAmbientPlayback } from "./ambientPlayback";

afterEach(() => vi.unstubAllGlobals());

function fixture() {
  vi.stubGlobal("Element", class {});
  const audio = Object.assign(new EventTarget(), {
    play: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
    pause: vi.fn(),
  });
  const gestures = new EventTarget();
  const blocked = vi.fn();
  const error = vi.fn();
  const start = () => startAmbientPlayback(
    audio, gestures, blocked, error,
  );
  return { audio, gestures, blocked, error, start };
}

describe("default ambient playback", () => {
  it("plays on mount and never restarts after successful playback or explicit pause", async () => {
    const { audio, gestures, start } = fixture();
    const stop = start();
    await vi.waitFor(() => expect(audio.play).toHaveBeenCalledOnce());
    audio.pause();
    gestures.dispatchEvent(new Event("pointerdown"));
    gestures.dispatchEvent(new Event("keydown"));
    expect(audio.play).toHaveBeenCalledOnce();
    stop();
    expect(audio.pause).toHaveBeenCalledTimes(2);
  });

  it.each(["pointerdown", "keydown"])("retries blocked autoplay on %s and then removes retries", async (type) => {
    const { audio, gestures, blocked, error, start } = fixture();
    audio.play.mockRejectedValueOnce(new DOMException("User interaction required", "NotAllowedError"));
    const stop = start();
    await vi.waitFor(() => expect(blocked).toHaveBeenCalledOnce());
    gestures.dispatchEvent(new Event(type));
    await vi.waitFor(() => expect(audio.play).toHaveBeenCalledTimes(2));
    gestures.dispatchEvent(new Event(type));
    expect(audio.play).toHaveBeenCalledTimes(2);
    expect(error).not.toHaveBeenCalled();
    stop();
  });

  it("surfaces non-policy errors and cancels pending startup on unmount", async () => {
    const { audio, gestures, blocked, error, start } = fixture();
    audio.play.mockRejectedValueOnce(new Error("File missing"));
    const stop = start();
    await vi.waitFor(() => expect(error).toHaveBeenCalledOnce());
    gestures.dispatchEvent(new Event("pointerdown"));
    expect(audio.play).toHaveBeenCalledOnce();
    expect(blocked).not.toHaveBeenCalled();
    stop();

    audio.play.mockRejectedValueOnce(new DOMException("Blocked", "NotAllowedError"));
    const cancel = start();
    cancel();
    await Promise.resolve();
    await Promise.resolve();
    gestures.dispatchEvent(new Event("pointerdown"));
    expect(audio.play).toHaveBeenCalledTimes(2);
    expect(blocked).not.toHaveBeenCalled();
  });

  it("does not undo a manual pause after the user explicitly enabled blocked audio", async () => {
    const { audio, gestures, blocked, start } = fixture();
    audio.play.mockRejectedValueOnce(new DOMException("Blocked", "NotAllowedError"));
    const stop = start();
    await vi.waitFor(() => expect(blocked).toHaveBeenCalledOnce());
    await audio.play();
    audio.dispatchEvent(new Event("playing"));
    audio.pause();
    gestures.dispatchEvent(new Event("pointerdown"));
    expect(audio.play).toHaveBeenCalledTimes(2);
    stop();
  });
});
