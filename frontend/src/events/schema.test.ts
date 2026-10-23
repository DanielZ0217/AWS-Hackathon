import { describe, expect, it } from "vitest";
import { isKnownType, parseWorkflowEvent } from "./schema";

const valid = {
  event_id: "evt-001",
  run_id: "run-001",
  sequence: 1,
  timestamp: "2026-10-23T14:00:00Z",
  type: "worker.started",
  summary: "Lab worker started",
  visibility: "demo_detail",
};

describe("parseWorkflowEvent", () => {
  it("parses a valid event and normalizes absent lists and payload", () => {
    const result = parseWorkflowEvent(valid);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.event.need_ids).toEqual([]);
      expect(result.event.payload).toEqual({});
    }
  });

  it("rejects an event missing sequence without throwing", () => {
    const { sequence: _omitted, ...withoutSequence } = valid;
    const result = parseWorkflowEvent(withoutSequence);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("sequence");
  });

  it("rejects an unknown visibility value", () => {
    const result = parseWorkflowEvent({ ...valid, visibility: "everyone" });
    expect(result.ok).toBe(false);
  });

  it("does not throw on non-object input", () => {
    expect(parseWorkflowEvent(null).ok).toBe(false);
    expect(parseWorkflowEvent("oops").ok).toBe(false);
  });

  it("accepts an unknown event type but flags it as not known", () => {
    const result = parseWorkflowEvent({ ...valid, type: "brand.new_event" });
    expect(result.ok).toBe(true);
    if (result.ok) expect(isKnownType(result.event)).toBe(false);
  });

  it("recognizes a known event type", () => {
    const result = parseWorkflowEvent(valid);
    expect(result.ok && isKnownType(result.event)).toBe(true);
  });

  it("keeps unknown extra fields", () => {
    const result = parseWorkflowEvent({ ...valid, backend_added: "x" });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.event.backend_added).toBe("x");
  });

  it("tolerates null for optional fields", () => {
    const result = parseWorkflowEvent({ ...valid, task_id: null, need_ids: null, payload: null });
    expect(result.ok).toBe(true);
  });
});
