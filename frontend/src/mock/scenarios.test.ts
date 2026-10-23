import { describe, expect, it } from "vitest";
import { TERMINAL_EVENT_TYPES, parseWorkflowEvent } from "../events/schema";
import { SCENARIOS, getScenario } from "./scenarios";

describe.each(SCENARIOS)("scenario $id", (scenario) => {
  it("has events that all pass the schema", () => {
    for (const { event } of scenario.events) {
      const result = parseWorkflowEvent(event);
      expect(result.ok, `${event.event_id}: ${result.ok ? "" : result.error}`).toBe(true);
    }
  });

  it("has strictly increasing sequence numbers starting at 1", () => {
    scenario.events.forEach(({ event }, index) => expect(event.sequence).toBe(index + 1));
  });

  it("has unique event ids and a single run id", () => {
    const ids = scenario.events.map(({ event }) => event.event_id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(scenario.events.map(({ event }) => event.run_id)).size).toBe(1);
  });

  it("has non-negative finite delays", () => {
    for (const { delayMs } of scenario.events) {
      expect(Number.isFinite(delayMs) && delayMs >= 0).toBe(true);
    }
  });

  it("ends with exactly one terminal event, and it is the last event", () => {
    const terminal = (scenario.events as { event: { type: string } }[]).filter(({ event }) =>
      (TERMINAL_EVENT_TYPES as readonly string[]).includes(event.type),
    );
    expect(terminal).toHaveLength(1);
    expect(scenario.events[scenario.events.length - 1].event.type).toBe(terminal[0].event.type);
  });

  it("has at least one patient-visible event", () => {
    expect(scenario.events.some(({ event }) => event.visibility === "patient")).toBe(true);
  });
});

describe("scenario behavior", () => {
  it("red-flag emits no answer sections", () => {
    const types = getScenario("red-flag")!.events.map(({ event }) => event.type);
    expect(types).toContain("review.required");
    expect(types).not.toContain("answer.section");
  });

  it("worker-failure contains a worker.failed and ends partial", () => {
    const types = getScenario("worker-failure")!.events.map(({ event }) => event.type);
    expect(types).toContain("worker.failed");
    expect(types[types.length - 1]).toBe("run.partial");
  });

  it("recovery runs exactly one recovery round", () => {
    const types = getScenario("recovery")!.events.map(({ event }) => event.type);
    expect(types.filter((t) => t === "recovery.granted")).toHaveLength(1);
  });
});
