import { describe, expect, it, vi } from "vitest";
import { SimulationClock, type FrameScheduler } from "./SimulationClock";

function manualScheduler(): FrameScheduler & { flush(timestampMs: number): void } {
  let pending: ((timestampMs: number) => void) | null = null;
  return {
    request(callback) {
      pending = callback;
      return 1;
    },
    cancel() {
      pending = null;
    },
    flush(timestampMs) {
      const callback = pending;
      pending = null;
      callback?.(timestampMs);
    },
  };
}

describe("SimulationClock", () => {
  it("advances simulated time according to the real seconds per simulated hour", () => {
    const clock = new SimulationClock({ realSecondsPerSimHour: 60, scheduler: manualScheduler() });
    clock.setRange(0, 7200);
    clock.play();
    clock.advance(100);
    // 60 s reelles = 1 h simulee -> 0,1 s reelle = 6 s simulees
    expect(clock.time).toBeCloseTo(6);
  });

  it("supports 1 simulated hour = 1 real second", () => {
    const clock = new SimulationClock({ realSecondsPerSimHour: 1, scheduler: manualScheduler() });
    clock.setRange(0, 7200);
    clock.play();
    clock.advance(200);
    expect(clock.time).toBeCloseTo(720);
  });

  it("allows changing the speed while playing", () => {
    const clock = new SimulationClock({ realSecondsPerSimHour: 60, scheduler: manualScheduler() });
    clock.setRange(0, 7200);
    clock.play();
    clock.advance(100);
    clock.setRealSecondsPerSimHour(10);
    clock.advance(100);
    expect(clock.time).toBeCloseTo(6 + 36);
    expect(clock.getSnapshot().isPlaying).toBe(true);
  });

  it("stops at the end of the range and restarts from the beginning", () => {
    const clock = new SimulationClock({ realSecondsPerSimHour: 1, scheduler: manualScheduler() });
    clock.setRange(10, 100);
    clock.play();
    clock.advance(200);
    expect(clock.time).toBe(100);
    expect(clock.getSnapshot().isPlaying).toBe(false);
    clock.play();
    expect(clock.time).toBe(10);
    clock.restart();
    expect(clock.time).toBe(10);
  });

  it("does not advance while paused and clamps seeks", () => {
    const clock = new SimulationClock({ scheduler: manualScheduler() });
    clock.setRange(0, 100);
    clock.advance(1000);
    expect(clock.time).toBe(0);
    clock.seek(500);
    expect(clock.time).toBe(100);
    clock.seek(-5);
    expect(clock.time).toBe(0);
  });

  it("drives every frame listener from a single scheduled loop", () => {
    const scheduler = manualScheduler();
    const requestSpy = vi.spyOn(scheduler, "request");
    const clock = new SimulationClock({ realSecondsPerSimHour: 3600, scheduler });
    clock.setRange(0, 1000);
    const first = vi.fn();
    const second = vi.fn();
    clock.onFrame(first);
    clock.onFrame(second);
    clock.play();
    scheduler.flush(0);
    scheduler.flush(100);
    expect(first).toHaveBeenLastCalledWith(clock.time);
    expect(second).toHaveBeenLastCalledWith(clock.time);
    expect(clock.time).toBeCloseTo(0.1);
    // Une seule requete en attente a la fois, quel que soit le nombre d'abonnes.
    expect(requestSpy).toHaveBeenCalledTimes(3);
  });

  it("throttles UI notifications during playback", () => {
    const scheduler = manualScheduler();
    const clock = new SimulationClock({ scheduler, uiIntervalMs: 100 });
    clock.setRange(0, 100000);
    const listener = vi.fn();
    clock.subscribe(listener);
    clock.play();
    listener.mockClear();
    for (let t = 0; t <= 1000; t += 16) {
      scheduler.flush(t);
    }
    expect(listener.mock.calls.length).toBeLessThanOrEqual(11);
    expect(listener.mock.calls.length).toBeGreaterThan(0);
  });

  it("rejects invalid ranges and speeds", () => {
    const clock = new SimulationClock({ scheduler: manualScheduler() });
    expect(() => clock.setRange(10, 0)).toThrow(RangeError);
    expect(() => clock.setRealSecondsPerSimHour(0)).toThrow(RangeError);
    expect(() => clock.setRealSecondsPerSimHour(Number.NaN)).toThrow(RangeError);
  });
});
