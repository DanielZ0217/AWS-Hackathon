import { z } from "zod";

// The ONE place that reads event payloads. The backend has not defined payload shapes yet,
// so every key name below is an ASSUMPTION. Each reader takes untyped data and returns a typed
// value, or null / [] when the data does not match. None of them throw, so a payload mismatch
// makes a card show less detail instead of crashing the page.

export type Payload = Record<string, unknown>;

// --- model calls -----------------------------------------------------------

export interface ModelCall {
  model: string;
  inputTokens: number | null; // null = unknown. Never guess usage.
  outputTokens: number | null;
  durationMs: number | null;
}

const ModelCallSchema = z.object({
  model: z.string(),
  input_tokens: z.number().nullish(),
  output_tokens: z.number().nullish(),
  duration_ms: z.number().nullish(),
});

export function readModelCall(payload: Payload): ModelCall | null {
  const parsed = ModelCallSchema.safeParse(payload.model_call);
  if (!parsed.success) return null;
  const call = parsed.data;
  return {
    model: call.model,
    inputTokens: call.input_tokens ?? null,
    outputTokens: call.output_tokens ?? null,
    durationMs: call.duration_ms ?? null,
  };
}

// --- red flags -------------------------------------------------------------

export interface RedFlag {
  id: string;
  description: string;
  supportingObservationIds: string[];
  requiresHumanReview: boolean;
}

const RedFlagSchema = z.object({
  flag_id: z.string(),
  description: z.string(),
  supporting_observation_ids: z.array(z.string()).nullish(),
  requires_human_review: z.boolean().nullish(),
});

export function readRedFlags(payload: Payload): RedFlag[] {
  if (!Array.isArray(payload.red_flags)) return [];
  return payload.red_flags.flatMap((item): RedFlag[] => {
    const parsed = RedFlagSchema.safeParse(item);
    if (!parsed.success) return [];
    return [
      {
        id: parsed.data.flag_id,
        description: parsed.data.description,
        supportingObservationIds: parsed.data.supporting_observation_ids ?? [],
        // If the backend does not say, assume the safe answer: a human must review.
        requiresHumanReview: parsed.data.requires_human_review ?? true,
      },
    ];
  });
}

// --- answer sections -------------------------------------------------------

export interface AnswerSection {
  id: string;
  order: number;
  title: string;
  text: string;
  evidenceIds: string[];
}

const AnswerSectionSchema = z.object({
  section_id: z.string(),
  order: z.number(),
  title: z.string(),
  text: z.string(),
});

export function readAnswerSection(payload: Payload, evidenceIds: string[] = []): AnswerSection | null {
  const parsed = AnswerSectionSchema.safeParse(payload);
  if (!parsed.success) return null;
  const { section_id, order, title, text } = parsed.data;
  return { id: section_id, order, title, text, evidenceIds };
}

// --- worker failures -------------------------------------------------------

export interface WorkerError {
  category: string | null;
  limitation: string | null;
  nextAction: string | null;
}

const WorkerErrorSchema = z.object({
  error_category: z.string().nullish(),
  limitation: z.string().nullish(),
  next_action: z.string().nullish(),
});

// Always returns an object: a failed worker is still shown as failed even with no details.
export function readWorkerError(payload: Payload): WorkerError {
  const parsed = WorkerErrorSchema.safeParse(payload);
  const data = parsed.success ? parsed.data : {};
  return {
    category: data.error_category ?? null,
    limitation: data.limitation ?? null,
    nextAction: data.next_action ?? null,
  };
}

// --- evidence ids ----------------------------------------------------------

// ASSUMPTION: evidence ids look like "ev-<worker>-<n>" (for example "ev-lab-1"). Returns the
// worker an evidence id came from, or null if the id does not follow that pattern.
export function readEvidenceWorker(evidenceId: string): string | null {
  const match = /^ev-([a-z_]+)-\d+$/i.exec(evidenceId);
  return match ? match[1] : null;
}

// --- small readers ---------------------------------------------------------

export function readRoutingQuestion(payload: Payload): string | null {
  return typeof payload.question === "string" ? payload.question : null;
}

export function readLimitations(payload: Payload): string[] {
  if (!Array.isArray(payload.limitations)) return [];
  return payload.limitations.filter((x): x is string => typeof x === "string");
}

export interface DoctorDecision {
  decision: string;
  reason: string | null;
}

export function readDoctorDecision(payload: Payload): DoctorDecision | null {
  if (typeof payload.decision !== "string") return null;
  return { decision: payload.decision, reason: typeof payload.reason === "string" ? payload.reason : null };
}

export interface ReviewRequired {
  flagIds: string[];
  resumable: boolean;
}

export function readReviewRequired(payload: Payload): ReviewRequired {
  const flagIds = Array.isArray(payload.flag_ids)
    ? payload.flag_ids.filter((x): x is string => typeof x === "string")
    : [];
  // Do not claim a run can be resumed unless the backend says so.
  return { flagIds, resumable: payload.resumable === true };
}

export interface RecoveryQuery {
  kind: string;
  text: string;
  isSearchAid: boolean; // the HyDE paragraph: a search aid, never accepted evidence
}

const RecoveryQuerySchema = z.object({
  kind: z.string(),
  text: z.string(),
  label: z.string().nullish(),
});

export function readRecoveryQueries(payload: Payload): RecoveryQuery[] {
  if (!Array.isArray(payload.queries)) return [];
  return payload.queries.flatMap((item): RecoveryQuery[] => {
    const parsed = RecoveryQuerySchema.safeParse(item);
    if (!parsed.success) return [];
    return [
      {
        kind: parsed.data.kind,
        text: parsed.data.text,
        isSearchAid: parsed.data.label === "generated_search_aid",
      },
    ];
  });
}

export interface TerminalInfo {
  outcome: string | null;
  limitations: string[];
  resumable: boolean;
}

export function readTerminalInfo(payload: Payload): TerminalInfo {
  return {
    outcome: typeof payload.outcome === "string" ? payload.outcome : null,
    limitations: readLimitations(payload),
    resumable: payload.resumable === true,
  };
}
