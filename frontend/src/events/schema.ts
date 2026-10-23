import { z } from "zod";

// Event types listed in architecture/05-generation-streaming-and-tracing.md (team repo).
// The UI has a dedicated rendering for these; anything else is shown as a generic row.
export const KNOWN_EVENT_TYPES = [
  "run.started",
  "intake.started",
  "intake.decomposed",
  "routing.assigned",
  "worker.started",
  "retrieval.started",
  "retrieval.completed",
  "graph.expanded",
  "rerank.completed",
  "evaluation.started",
  "evaluation.passed",
  "evaluation.insufficient",
  "recovery.requested",
  "recovery.granted",
  "recovery.denied",
  "recovery.queries_generated",
  "recovery.completed",
  "worker.completed",
  "worker.failed",
  "worker.timed_out",
  "doctor.review_completed",
  "guidance.started",
  "guidance.checked",
  "review.required",
  "answer.started",
  "answer.section",
  "answer.completed",
  "run.completed",
  "run.partial",
  "run.failed",
  "run.cancelled",
  "run.paused",
] as const;

export type KnownEventType = (typeof KNOWN_EVENT_TYPES)[number];

// A run ends with exactly one of these (run.paused = waiting for human review).
export const TERMINAL_EVENT_TYPES = [
  "run.completed",
  "run.partial",
  "run.failed",
  "run.cancelled",
  "run.paused",
] as const;

// Drives the patient / audit toggle.
export const VisibilitySchema = z.enum(["patient", "demo_detail", "operator"]);
export type Visibility = z.infer<typeof VisibilitySchema>;

// The backend may send null for an absent id list; normalize both to [].
const IdList = z
  .array(z.string())
  .nullish()
  .transform((v) => v ?? []);

// Envelope from the Layer 5 `WorkflowEvent`. Fields the UI cannot work without are strict.
// Fields the doc leaves undefined (status values, layer type, timestamp format, payload
// contents) are lenient until the backend's real format is known.
// looseObject keeps unknown extra fields instead of stripping or rejecting them.
export const WorkflowEventSchema = z.looseObject({
  // --- strict: the UI depends on these ---
  event_id: z.string().min(1),
  run_id: z.string().min(1),
  sequence: z.number().int().nonnegative(),
  timestamp: z.union([z.string(), z.number()]),
  type: z.string().min(1),
  summary: z.string(),
  visibility: VisibilitySchema,

  // --- lenient: documented but loosely specified ---
  schema_version: z.union([z.string(), z.number()]).nullish(),
  trace_id: z.string().nullish(),
  span_id: z.string().nullish(),
  parent_span_id: z.string().nullish(),
  layer: z.union([z.string(), z.number()]).nullish(),
  node: z.string().nullish(),
  task_id: z.string().nullish(),
  need_ids: IdList,
  status: z.string().nullish(),
  source_worker: z.string().nullish(),
  destination_worker: z.string().nullish(),
  artifact_ids: IdList,
  evidence_ids: IdList,
  review_version: z.union([z.string(), z.number()]).nullish(),
  retrieval_round: z.number().nullish(),
  strategy: z.string().nullish(),
  payload: z
    .record(z.string(), z.unknown())
    .nullish()
    .transform((v) => v ?? {}),
});

export type WorkflowEvent = z.infer<typeof WorkflowEventSchema>;

export type ParseResult =
  | { ok: true; event: WorkflowEvent }
  | { ok: false; error: string; raw: unknown };

// Never throws. A bad message becomes { ok: false } so the timeline can show an
// "unrecognized event" row instead of crashing the page.
export function parseWorkflowEvent(raw: unknown): ParseResult {
  const result = WorkflowEventSchema.safeParse(raw);
  if (result.success) return { ok: true, event: result.data };
  const error = result.error.issues
    .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
    .join("; ");
  return { ok: false, error, raw };
}

// True if the UI has a dedicated rendering for this event's type.
export function isKnownType(event: Pick<WorkflowEvent, "type">): boolean {
  return (KNOWN_EVENT_TYPES as readonly string[]).includes(event.type);
}
