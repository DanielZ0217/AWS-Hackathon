import { describe, expect, it } from "vitest";
import type { WorkflowEvent } from "../events/schema";
import { decisionLabel, shortModelName, stepLabel, workerColor } from "../labels";
import { getScenario } from "../mock/scenarios";
import { readEvidenceWorker } from "../state/payloadAdapters";
import { createInitialState, ingestRaw } from "../state/runState";
import { buildSummaryModel } from "./summaryModel";

function summaryOf(id: string, take?: number) {
  const events: WorkflowEvent[] = getScenario(id)!.events.map((s) => s.event);
  const run = events.slice(0, take).reduce<ReturnType<typeof createInitialState>>(ingestRaw, createInitialState());
  return buildSummaryModel(run);
}

describe("buildSummaryModel", () => {
  it("idle before any event", () => {
    expect(buildSummaryModel(createInitialState()).stage).toBe("idle");
  });

  it("working while events arrive but no sections exist yet", () => {
    expect(summaryOf("clean", 9).stage).toBe("working");
  });

  it("clean: ready with four sections, no gaps, a stated limitation", () => {
    const summary = summaryOf("clean");
    expect(summary.stage).toBe("ready");
    expect(summary.sections).toHaveLength(4);
    expect(summary.gaps).toEqual([]);
    expect(summary.limitations).toEqual(["Prototype output. Not clinical clearance."]);
  });

  it("names the specialists a section rests on, in plain words", () => {
    expect(summaryOf("clean").sections[0].basedOn).toEqual(["Lab results", "Chest image", "Heart rhythm"]);
  });

  it("red-flag: review stage and no sections", () => {
    const summary = summaryOf("red-flag");
    expect(summary.stage).toBe("review");
    expect(summary.sections).toHaveLength(0);
  });

  it("worker-failure: ready, with the missing part named and a next step", () => {
    const summary = summaryOf("worker-failure");
    expect(summary.stage).toBe("ready");
    expect(summary.gaps).toEqual(["Chest image couldn't be reviewed. Clinical re-evaluation requested."]);
  });

  it("recovery: ready with two sections and no gaps", () => {
    const summary = summaryOf("recovery");
    expect(summary.stage).toBe("ready");
    expect(summary.sections).toHaveLength(2);
    expect(summary.gaps).toEqual([]);
  });
});

describe("label helpers", () => {
  it("decisionLabel gives plain words and falls back to the raw value", () => {
    expect(decisionLabel("proceed")).toBe("Enough support for an explanation");
    expect(decisionLabel("human_review")).toBe("A healthcare professional must review this");
    expect(decisionLabel("something_new")).toBe("something_new");
    expect(decisionLabel(null)).toBe("No decision reported");
  });

  it("stepLabel names workers and known steps, and falls back to the raw name", () => {
    expect(stepLabel("lab")).toBe("Lab results");
    expect(stepLabel("intake.decomposed")).toBe("Organizing the request");
    expect(stepLabel("something.else")).toBe("something.else");
  });

  it("shortModelName drops the routing prefix", () => {
    expect(shortModelName("us.anthropic.claude-sonnet-4-6")).toBe("claude-sonnet-4-6");
    expect(shortModelName("global.anthropic.claude-haiku-5-5")).toBe("claude-haiku-5-5");
    expect(shortModelName("amazon.nova-lite-v1:0")).toBe("amazon.nova-lite-v1:0");
  });

  it("workerColor uses the specialist hue and a neutral fallback", () => {
    expect(workerColor("lab")).toBe("var(--color-lab)");
    expect(workerColor("unknown")).toBe("var(--color-ink-soft)");
  });

  it("readEvidenceWorker reads the worker from an evidence id", () => {
    expect(readEvidenceWorker("ev-lab-1")).toBe("lab");
    expect(readEvidenceWorker("ev-radiology-12")).toBe("radiology");
    expect(readEvidenceWorker("passage-7")).toBeNull();
  });
});
