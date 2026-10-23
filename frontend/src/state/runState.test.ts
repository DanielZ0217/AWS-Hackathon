import { describe, expect, it } from "vitest";
import type { WorkflowEvent } from "../events/schema";
import { SCENARIOS, getScenario } from "../mock/scenarios";
import {
  applyEvent,
  buildRunState,
  createInitialState,
  ingestRaw,
  modelCallTotals,
  visibleEvents,
} from "./runState";

function eventsOf(id: string): WorkflowEvent[] {
  return getScenario(id)!.events.map((s) => s.event);
}

function feed(events: unknown[]) {
  return events.reduce<ReturnType<typeof createInitialState>>((state, raw) => ingestRaw(state, raw), createInitialState());
}

const worker = (state: ReturnType<typeof createInitialState>, name: string) =>
  state.workers.find((w) => w.worker === name)!;

describe("final state per scenario", () => {
  it("clean: completed with three succeeded workers and four sections", () => {
    const state = feed(eventsOf("clean"));
    expect(state.status).toBe("completed");
    expect(state.workers.map((w) => w.status)).toEqual(["succeeded", "succeeded", "succeeded"]);
    expect(state.workers.map((w) => w.worker)).toEqual(["lab", "radiology", "ecg"]);
    expect(state.answer.status).toBe("completed");
    expect(state.answer.sections).toHaveLength(4);
    expect(state.redFlags).toHaveLength(0);
    expect(state.doctor?.decision).toBe("proceed");
    expect(state.rejected).toHaveLength(0);
  });

  it("red-flag: paused with one flag, review required, and no answer sections", () => {
    const state = feed(eventsOf("red-flag"));
    expect(state.status).toBe("paused");
    expect(state.redFlags.map((f) => f.id)).toEqual(["flag-001"]);
    expect(state.review.required).toBe(true);
    expect(state.review.flagIds).toEqual(["flag-001"]);
    expect(state.review.resumable).toBe(true);
    expect(state.answer.sections).toHaveLength(0);
    expect(state.doctor?.decision).toBe("human_review");
    expect(state.outcome?.type).toBe("run.paused");
  });

  it("worker-failure: partial, radiology failed with error details, three sections", () => {
    const state = feed(eventsOf("worker-failure"));
    expect(state.status).toBe("partial");
    expect(worker(state, "radiology").status).toBe("failed");
    expect(worker(state, "radiology").error).toEqual({
      category: "analysis_unavailable",
      limitation: "Chest image could not be analyzed.",
      nextAction: "Clinical re-evaluation requested.",
    });
    expect(state.answer.sections).toHaveLength(3);
  });

  it("recovery: one recovery round, labeled search aid, radiology at round 2", () => {
    const state = feed(eventsOf("recovery"));
    expect(state.status).toBe("completed");
    expect(state.recovery).toMatchObject({ requested: true, granted: true, denied: false, completed: true });
    expect(state.recovery.queries).toHaveLength(3);
    expect(state.recovery.queries.filter((q) => q.isSearchAid)).toHaveLength(1);
    expect(worker(state, "radiology").retrievalRound).toBe(2);
    expect(worker(state, "radiology").status).toBe("succeeded");
    expect(state.answer.sections).toHaveLength(2);
  });
});

describe("mid-run state", () => {
  it("after the first nine events: running, three workers running with their questions", () => {
    const state = feed(eventsOf("clean").slice(0, 9));
    expect(state.status).toBe("running");
    expect(state.workers).toHaveLength(3);
    expect(state.workers.every((w) => w.status === "running" && w.question !== null)).toBe(true);
    expect(state.outcome).toBeNull();
  });

  it("no events: idle", () => {
    expect(createInitialState().status).toBe("idle");
  });
});

describe("robustness", () => {
  it("is idempotent: feeding every event twice equals feeding once", () => {
    const events = eventsOf("recovery");
    expect(feed([...events, ...events])).toEqual(feed(events));
  });

  it("is order independent: reversed and interleaved arrival give the same state", () => {
    const events = eventsOf("clean");
    const expected = feed(events);
    expect(feed([...events].reverse())).toEqual(expected);
    const interleaved = [...events.filter((_, i) => i % 2 === 1), ...events.filter((_, i) => i % 2 === 0)];
    expect(feed(interleaved)).toEqual(expected);
  });

  it("returns the same state object for a repeated event", () => {
    const events = eventsOf("clean");
    const state = feed(events);
    expect(applyEvent(state, events[3])).toBe(state);
  });

  it("rejects an event from a different run and records the reason", () => {
    const state = feed(eventsOf("clean"));
    const foreign = eventsOf("red-flag")[0];
    const next = applyEvent(state, foreign);
    expect(next.events).toHaveLength(state.events.length);
    expect(next.rejected).toHaveLength(1);
    expect(next.rejected[0].reason).toContain("run");
  });

  it("rejects a conflicting duplicate event_id (first one wins)", () => {
    const events = eventsOf("clean");
    const state = feed(events);
    const next = applyEvent(state, { ...events[2], summary: "tampered" });
    expect(next.rejected).toHaveLength(1);
    expect(next.events.find((e) => e.event_id === events[2].event_id)?.summary).toBe(events[2].summary);
  });

  it("records a malformed message instead of throwing, leaving the rest unchanged", () => {
    const state = feed(eventsOf("clean").slice(0, 5));
    const next = ingestRaw(state, { event_id: "bad-1", nonsense: true });
    expect(next.events).toEqual(state.events);
    expect(next.rejected).toHaveLength(1);
    expect(next.rejected[0].eventId).toBe("bad-1");
    expect(ingestRaw(state, null).rejected).toHaveLength(1);
  });

  it("freezes the result after the terminal event but keeps late events in the timeline", () => {
    const events = eventsOf("clean");
    const last = events[events.length - 1];
    const late: WorkflowEvent = {
      ...last,
      event_id: "late-1",
      sequence: last.sequence + 1,
      type: "answer.section",
      payload: { section_id: "late", order: 99, title: "Late", text: "Late text" },
    };
    const state = feed([...events, late]);
    expect(state.answer.sections).toHaveLength(4);
    expect(state.status).toBe("completed");
    expect(state.events).toHaveLength(events.length + 1);
  });

  it("never removes a red flag when later events arrive", () => {
    const events = eventsOf("red-flag");
    const afterFlag = events.findIndex((e) => e.type === "worker.completed" && e.node === "ecg");
    const early = feed(events.slice(0, afterFlag + 1));
    const full = feed(events);
    expect(early.redFlags).toHaveLength(1);
    expect(full.redFlags).toEqual(early.redFlags);
  });
});

describe("model-call ledger", () => {
  it("clean scenario: six calls with hand-computed totals", () => {
    // decomposition 1180/340/820, three workers 2100/520/1400 each, doctor 3400/610/1900, guidance 1900/260/900
    const state = feed(eventsOf("clean"));
    expect(modelCallTotals(state)).toEqual({ calls: 6, inputTokens: 12780, outputTokens: 2770, durationMs: 7820 });
    expect(worker(state, "lab").modelCalls).toHaveLength(1);
  });

  it("every scenario's ledger matches the number of model_call payloads", () => {
    for (const scenario of SCENARIOS) {
      const expected = scenario.events.filter(({ event }) => "model_call" in event.payload).length;
      expect(feed(scenario.events.map((s) => s.event)).modelCalls).toHaveLength(expected);
    }
  });
});

describe("visibleEvents", () => {
  it("patient is a strict subset of audit, and operator shows everything", () => {
    const state = feed(eventsOf("clean"));
    const patient = visibleEvents(state, "patient");
    const audit = visibleEvents(state, "audit");
    expect(patient.length).toBeGreaterThan(0);
    expect(patient.length).toBeLessThan(audit.length);
    expect(patient.every((e) => e.visibility === "patient")).toBe(true);
    expect(visibleEvents(state, "operator")).toHaveLength(state.events.length);
  });
});

describe("buildRunState", () => {
  it("does not mutate its input array", () => {
    const events = [...eventsOf("clean")].reverse();
    const snapshot = events.map((e) => e.event_id);
    buildRunState(events);
    expect(events.map((e) => e.event_id)).toEqual(snapshot);
  });
});
