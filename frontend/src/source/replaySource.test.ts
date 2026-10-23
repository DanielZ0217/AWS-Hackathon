import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkflowEvent } from "../events/schema";
import type { Scenario } from "../mock/scenarios";
import { ReplaySource } from "./replaySource";
import type { ConnectionStatus, SourceListener } from "./types";

function makeScenario(delays: number[]): Scenario {
  return {
    id: "t",
    label: "t",
    description: "",
    events: delays.map((delayMs, i) => ({
      delayMs,
      event: {
        event_id: `e${i + 1}`,
        run_id: "r",
        sequence: i + 1,
        timestamp: "2026-10-23T14:00:00Z",
        type: "intake.started",
        summary: `event ${i + 1}`,
        visibility: "demo_detail",
        need_ids: [],
        artifact_ids: [],
        evidence_ids: [],
        payload: {},
      },
    })),
  };
}

function record(source: ReplaySource) {
  const messages: string[] = [];
  const statuses: ConnectionStatus[] = [];
  const counts = { resets: 0 };
  const unsubscribe = source.subscribe({
    onMessage: (raw) => messages.push((raw as { event_id: string }).event_id),
    onStatus: (status) => statuses.push(status),
    onReset: () => {
      counts.resets += 1;
    },
  });
  return { messages, statuses, counts, unsubscribe };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ReplaySource timing", () => {
  it("emits events in order at the scripted times", () => {
    const source = new ReplaySource(makeScenario([0, 400, 300]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0);
    expect(rec.messages).toEqual(["e1"]);
    vi.advanceTimersByTime(399);
    expect(rec.messages).toEqual(["e1"]);
    vi.advanceTimersByTime(1);
    expect(rec.messages).toEqual(["e1", "e2"]);
    vi.advanceTimersByTime(299);
    expect(rec.messages).toEqual(["e1", "e2"]);
    vi.advanceTimersByTime(1);
    expect(rec.messages).toEqual(["e1", "e2", "e3"]);
  });

  it("at 2x speed the waits are halved", () => {
    const source = new ReplaySource(makeScenario([0, 400]), 2);
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0);
    vi.advanceTimersByTime(199);
    expect(rec.messages).toEqual(["e1"]);
    vi.advanceTimersByTime(1);
    expect(rec.messages).toEqual(["e1", "e2"]);
  });

  it("reaches 'ended' after the last event and reports full progress", () => {
    const source = new ReplaySource(makeScenario([0, 100, 100]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(200);
    expect(rec.statuses[rec.statuses.length - 1]).toBe("ended");
    expect(source.progress).toEqual({ emitted: 3, total: 3 });
  });

  it("ends immediately for an empty scenario", () => {
    const source = new ReplaySource(makeScenario([]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0);
    expect(rec.statuses[rec.statuses.length - 1]).toBe("ended");
    expect(rec.messages).toEqual([]);
  });
});

describe("pause, resume and speed", () => {
  it("pause stops emission and resume waits only the remaining time", () => {
    const source = new ReplaySource(makeScenario([0, 400, 300]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0); // e1
    vi.advanceTimersByTime(150); // 150 of the 400 ms wait for e2 has elapsed
    source.pause();
    expect(rec.statuses[rec.statuses.length - 1]).toBe("paused");
    vi.advanceTimersByTime(10_000);
    expect(rec.messages).toEqual(["e1"]);
    source.resume();
    vi.advanceTimersByTime(249);
    expect(rec.messages).toEqual(["e1"]);
    vi.advanceTimersByTime(1);
    expect(rec.messages).toEqual(["e1", "e2"]);
  });

  it("changing speed mid-wait rescales the remaining time", () => {
    const source = new ReplaySource(makeScenario([0, 400]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0); // e1
    vi.advanceTimersByTime(200); // half of the wait is done: 200 unscaled ms left
    source.setSpeed(2); // now 100 real ms left
    vi.advanceTimersByTime(99);
    expect(rec.messages).toEqual(["e1"]);
    vi.advanceTimersByTime(1);
    expect(rec.messages).toEqual(["e1", "e2"]);
  });

  it("ignores invalid speed values", () => {
    const source = new ReplaySource(makeScenario([0, 100]));
    const rec = record(source);
    source.setSpeed(0);
    source.setSpeed(-3);
    source.setSpeed(Number.NaN);
    source.start();
    vi.advanceTimersByTime(0);
    vi.advanceTimersByTime(100);
    expect(rec.messages).toEqual(["e1", "e2"]);
  });
});

describe("start, stop and restart", () => {
  it("restart resets the listener and replays from the first event", () => {
    const source = new ReplaySource(makeScenario([0, 100]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(100);
    expect(rec.counts.resets).toBe(1);
    source.restart();
    expect(rec.counts.resets).toBe(2);
    vi.advanceTimersByTime(0);
    expect(rec.messages).toEqual(["e1", "e2", "e1"]);
  });

  it("stop cancels everything and returns to idle", () => {
    const source = new ReplaySource(makeScenario([0, 100, 100]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0);
    source.stop();
    vi.advanceTimersByTime(10_000);
    expect(rec.messages).toEqual(["e1"]);
    expect(rec.statuses[rec.statuses.length - 1]).toBe("idle");
  });

  it("calling start twice does not schedule twice", () => {
    const source = new ReplaySource(makeScenario([0, 100]));
    const rec = record(source);
    source.start();
    source.start();
    vi.advanceTimersByTime(0);
    expect(rec.messages).toEqual(["e1"]);
    expect(rec.counts.resets).toBe(1);
  });
});

describe("listeners", () => {
  it("an unsubscribed listener receives nothing more", () => {
    const source = new ReplaySource(makeScenario([0, 100]));
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(0);
    rec.unsubscribe();
    vi.advanceTimersByTime(100);
    expect(rec.messages).toEqual(["e1"]);
  });

  it("delivers a copy: changing a delivered event does not change the scenario", () => {
    const scenario = makeScenario([0]);
    const source = new ReplaySource(scenario);
    let received: WorkflowEvent | undefined;
    source.subscribe({ onMessage: (raw) => (received = raw as WorkflowEvent), onStatus: () => {}, onReset: () => {} });
    source.start();
    vi.advanceTimersByTime(0);
    received!.summary = "changed";
    expect(scenario.events[0].event.summary).toBe("event 1");
  });

  it("a throwing listener does not stop the replay or starve other listeners", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const source = new ReplaySource(makeScenario([0, 100]));
    const bad: SourceListener = {
      onMessage: () => {
        throw new Error("boom");
      },
      onStatus: () => {},
      onReset: () => {},
    };
    source.subscribe(bad);
    const rec = record(source);
    source.start();
    vi.advanceTimersByTime(100);
    expect(rec.messages).toEqual(["e1", "e2"]);
    expect(errorSpy).toHaveBeenCalled();
    errorSpy.mockRestore();
  });

  it("tells a new subscriber the current status immediately", () => {
    const source = new ReplaySource(makeScenario([0]));
    const rec = record(source);
    expect(rec.statuses).toEqual(["idle"]);
  });
});
