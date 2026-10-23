import { describe, expect, it } from "vitest";
import { TERMINAL_EVENT_TYPES, parseWorkflowEvent } from "../events/schema";
import { createInitialState, ingestRaw } from "../state/runState";
import { RECORDED } from "./recorded";

const finalState = (id: string) => {
  const scenario = RECORDED.find((s) => s.id === id)!;
  return scenario.events.reduce<ReturnType<typeof createInitialState>>((state, { event }) => ingestRaw(state, event), createInitialState());
};

describe("recorded real runs", () => {
  it("has the three visits of the demo patient", () => {
    expect(RECORDED.map((s) => s.id)).toEqual(["VP01-v1", "VP01-v2", "VP01-v3"]);
  });

  for (const scenario of RECORDED) {
    describe(scenario.id, () => {
      it("has events that all pass the schema, with sequences 1..N and unique ids", () => {
        scenario.events.forEach(({ event }, i) => {
          expect(parseWorkflowEvent(event).ok, event.event_id).toBe(true);
          expect(event.sequence).toBe(i + 1);
        });
        expect(new Set(scenario.events.map(({ event }) => event.event_id)).size).toBe(scenario.events.length);
      });

      it("ends with exactly one terminal event", () => {
        const terminal = scenario.events.filter(({ event }) => (TERMINAL_EVENT_TYPES as readonly string[]).includes(event.type));
        expect(terminal).toHaveLength(1);
        expect(scenario.events.at(-1)!.event.type).toBe(terminal[0].event.type);
      });

      it("has bounded replay delays so a rehearsal never sits idle", () => {
        for (const { delayMs } of scenario.events.slice(1)) {
          expect(delayMs).toBeGreaterThanOrEqual(150);
          expect(delayMs).toBeLessThanOrEqual(2500);
        }
      });

      it("contains no placeholder or mock text", () => {
        expect(JSON.stringify(scenario.events)).not.toMatch(/placeholder|mock mode/i);
      });

      it("carries the dataset warning that the ECG and X-ray are from two different people", () => {
        const state = finalState(scenario.id);
        expect(state.outcome?.limitations.some((l) => l.includes("two different real people"))).toBe(true);
      });
    });
  }

  it("visit 1 stops for human review with both red flags and no summary", () => {
    const state = finalState("VP01-v1");
    expect(state.status).toBe("paused");
    expect(state.review.required).toBe(true);
    expect(state.redFlags.map((f) => f.id).sort()).toEqual(["flag-ecg_report", "flag-xray_edema"]);
    expect(state.answer.sections).toHaveLength(0);
  });

  it("visits 2 and 3 complete with a four-section summary and no red flags", () => {
    for (const id of ["VP01-v2", "VP01-v3"]) {
      const state = finalState(id);
      expect(state.status, id).toBe("completed");
      expect(state.answer.sections, id).toHaveLength(4);
      expect(state.redFlags, id).toHaveLength(0);
      expect(state.workers.map((w) => w.worker).sort(), id).toEqual(["ecg", "radiology"]);
    }
  });
});
