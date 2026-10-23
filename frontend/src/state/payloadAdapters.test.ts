import { describe, expect, it } from "vitest";
import {
  readAnswerSection,
  readDoctorDecision,
  readLimitations,
  readModelCall,
  readRecoveryQueries,
  readRedFlags,
  readReviewRequired,
  readWorkerError,
} from "./payloadAdapters";

describe("readModelCall", () => {
  it("reads a complete model call", () => {
    const payload = { model_call: { model: "m", input_tokens: 10, output_tokens: 5, duration_ms: 200 } };
    expect(readModelCall(payload)).toEqual({ model: "m", inputTokens: 10, outputTokens: 5, durationMs: 200 });
  });

  it("keeps unknown usage as null instead of guessing", () => {
    expect(readModelCall({ model_call: { model: "m" } })).toEqual({
      model: "m",
      inputTokens: null,
      outputTokens: null,
      durationMs: null,
    });
  });

  it("returns null for a missing or malformed model call", () => {
    expect(readModelCall({})).toBeNull();
    expect(readModelCall({ model_call: "nope" })).toBeNull();
    expect(readModelCall({ model_call: { input_tokens: 5 } })).toBeNull();
  });
});

describe("readRedFlags", () => {
  it("reads valid flags and skips malformed entries", () => {
    const flags = readRedFlags({
      red_flags: [{ flag_id: "f1", description: "d", requires_human_review: false }, { nope: true }, "text"],
    });
    expect(flags).toHaveLength(1);
    expect(flags[0].id).toBe("f1");
    expect(flags[0].requiresHumanReview).toBe(false);
  });

  it("assumes human review is required when the field is absent", () => {
    const [flag] = readRedFlags({ red_flags: [{ flag_id: "f1", description: "d" }] });
    expect(flag.requiresHumanReview).toBe(true);
  });

  it("returns [] when red_flags is not an array", () => {
    expect(readRedFlags({ red_flags: "x" })).toEqual([]);
    expect(readRedFlags({})).toEqual([]);
  });
});

describe("readAnswerSection", () => {
  it("reads a section and attaches evidence ids", () => {
    const section = readAnswerSection({ section_id: "s1", order: 2, title: "T", text: "X" }, ["ev-1"]);
    expect(section).toEqual({ id: "s1", order: 2, title: "T", text: "X", evidenceIds: ["ev-1"] });
  });

  it("returns null when a required field is missing", () => {
    expect(readAnswerSection({ section_id: "s1", order: 1, text: "X" })).toBeNull();
  });
});

describe("readWorkerError", () => {
  it("returns all-null details for an empty payload", () => {
    expect(readWorkerError({})).toEqual({ category: null, limitation: null, nextAction: null });
  });

  it("reads error details", () => {
    expect(readWorkerError({ error_category: "c", limitation: "l", next_action: "n" })).toEqual({
      category: "c",
      limitation: "l",
      nextAction: "n",
    });
  });
});

describe("small readers", () => {
  it("readLimitations keeps only strings", () => {
    expect(readLimitations({ limitations: ["a", 1, "b"] })).toEqual(["a", "b"]);
    expect(readLimitations({ limitations: "a" })).toEqual([]);
  });

  it("readDoctorDecision needs a string decision", () => {
    expect(readDoctorDecision({})).toBeNull();
    expect(readDoctorDecision({ decision: "proceed" })).toEqual({ decision: "proceed", reason: null });
  });

  it("readReviewRequired does not claim resumable by default", () => {
    expect(readReviewRequired({})).toEqual({ flagIds: [], resumable: false });
    expect(readReviewRequired({ flag_ids: ["f1"], resumable: true })).toEqual({ flagIds: ["f1"], resumable: true });
  });

  it("readRecoveryQueries marks the labeled search aid", () => {
    const queries = readRecoveryQueries({
      queries: [
        { kind: "paraphrase", text: "a" },
        { kind: "hyde", text: "b", label: "generated_search_aid" },
        { bad: true },
      ],
    });
    expect(queries).toHaveLength(2);
    expect(queries.map((q) => q.isSearchAid)).toEqual([false, true]);
  });
});
