import { describe, expect, it } from "vitest";
import type { WorkflowEvent } from "../events/schema";
import { markLabel, statusLabel, workerLabel } from "../labels";
import { getScenario } from "../mock/scenarios";
import { createInitialState, ingestRaw } from "../state/runState";
import { buildStripModel } from "./stripModel";

function eventsOf(id: string): WorkflowEvent[] {
  return getScenario(id)!.events.map((s) => s.event);
}

function model(events: unknown[]) {
  return buildStripModel(events.reduce<ReturnType<typeof createInitialState>>(ingestRaw, createInitialState()));
}

const kinds = (m: ReturnType<typeof model>) => m.marks.map((x) => `${x.row}:${x.kind}`);

describe("buildStripModel", () => {
  it("is empty before any event", () => {
    const m = model([]);
    expect(m.rows).toEqual([]);
    expect(m.marks).toEqual([]);
    expect(m.columnCount).toBe(0);
    expect(m.frozen).toBe(false);
    expect(m.alarmColumn).toBeNull();
  });

  it("clean: four rows, eight columns in event order, three handoffs to the doctor", () => {
    const m = model(eventsOf("clean"));
    expect(m.rows.map((r) => r.id)).toEqual(["lab", "radiology", "ecg", "doctor_synthesis"]);
    expect(kinds(m)).toEqual([
      "lab:started",
      "radiology:started",
      "ecg:started",
      "lab:completed",
      "ecg:completed",
      "radiology:completed",
      "doctor_synthesis:reviewed",
      "doctor_synthesis:checked",
    ]);
    expect(m.marks.map((x) => x.col)).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
    expect(m.columnCount).toBe(8);
    expect(m.handoffs).toHaveLength(3);
    expect(m.handoffs.every((h) => h.kind === "result" && h.toCol === 6)).toBe(true);
    expect(m.bars.every((b) => !b.open)).toBe(true);
    expect(m.frozen).toBe(false);
    expect(m.alarmColumn).toBeNull();
  });

  it("mid-run: three open bars and no handoffs yet", () => {
    const m = model(eventsOf("clean").slice(0, 9));
    expect(m.marks).toHaveLength(3);
    expect(m.bars).toHaveLength(3);
    expect(m.bars.every((b) => b.open && b.toCol === 2)).toBe(true);
    expect(m.handoffs).toEqual([]);
    expect(m.rows.find((r) => r.id === "doctor_synthesis")?.status).toBe("waiting");
  });

  it("red-flag: freezes, marks the alarm at the flagged worker, shows review needed", () => {
    const m = model(eventsOf("red-flag"));
    expect(m.frozen).toBe(true);
    expect(m.rows.find((r) => r.id === "doctor_synthesis")?.status).toBe("needs_review");
    expect(kinds(m)).toContain("doctor_synthesis:review_required");
    const ecgDone = m.marks.find((x) => x.row === "ecg" && x.kind === "completed")!;
    expect(ecgDone.flagged).toBe(true);
    expect(m.alarmColumn).toBe(ecgDone.col);
  });

  it("worker-failure: the failed worker reaches the doctor as a gap, not a result", () => {
    const m = model(eventsOf("worker-failure"));
    expect(m.rows.find((r) => r.id === "radiology")?.status).toBe("failed");
    const byRow = Object.fromEntries(m.handoffs.map((h) => [h.fromRow, h.kind]));
    expect(byRow).toEqual({ lab: "result", ecg: "result", radiology: "gap" });
  });

  it("recovery: searching, gap, recovery and verified marks on the radiology row, in order", () => {
    const m = model(eventsOf("recovery"));
    const radiology = m.marks.filter((x) => x.row === "radiology").map((x) => x.kind);
    expect(radiology).toEqual(["started", "searching", "gap", "recovery", "verified", "completed"]);
    expect(m.columnCount).toBe(12);
    const bar = m.bars.find((b) => b.row === "radiology")!;
    expect(bar).toMatchObject({ fromCol: 1, toCol: 9, open: false });
  });

  it("gives the same strip regardless of arrival order", () => {
    const events = eventsOf("recovery");
    expect(model([...events].reverse())).toEqual(model(events));
  });

  it("ignores events after the terminal event", () => {
    const events = eventsOf("clean");
    const last = events[events.length - 1];
    const late: WorkflowEvent = { ...last, event_id: "late", sequence: last.sequence + 1, type: "worker.started", node: "lab" };
    expect(model([...events, late]).marks).toHaveLength(model(events).marks.length);
  });

  it("every mark has a non-empty customer-facing label", () => {
    for (const id of ["clean", "red-flag", "worker-failure", "recovery"]) {
      expect(model(eventsOf(id)).marks.every((x) => x.label.length > 0)).toBe(true);
    }
  });
});

describe("labels", () => {
  it("maps known workers to plain names and falls back to the raw name", () => {
    expect(workerLabel("radiology")).toBe("Chest image");
    expect(workerLabel("ecg")).toBe("Heart rhythm");
    expect(workerLabel("some_new_worker")).toBe("some_new_worker");
  });

  it("has customer-facing words for every status and mark kind used", () => {
    expect(statusLabel("failed")).toBe("Couldn't review");
    expect(statusLabel("waiting")).toBe("Waiting");
    expect(statusLabel("needs_review")).toBe("Waiting for review");
    expect(markLabel("review_required")).toBe("Review needed");
  });
});
