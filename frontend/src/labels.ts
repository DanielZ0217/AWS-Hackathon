import type { RunStatus, WorkerStatus } from "./state/runState";

// Customer-facing words live here, so the screens never show system names like "radiology worker".

export const DOCTOR_ROW = "doctor_synthesis";

const WORKER_LABELS: Record<string, string> = {
  lab: "Lab results",
  radiology: "Chest image",
  ecg: "Heart rhythm",
  [DOCTOR_ROW]: "Doctor review",
  nutrition: "Food and nutrition",
  physio: "Movement and exercise",
};

// An unknown worker falls back to its raw name rather than disappearing.
export function workerLabel(worker: string): string {
  return WORKER_LABELS[worker] ?? worker;
}

const WORKER_COLORS: Record<string, string> = {
  lab: "var(--color-lab)",
  radiology: "var(--color-radiology)",
  ecg: "var(--color-ecg)",
  [DOCTOR_ROW]: "var(--color-ink)",
};

export function workerColor(worker: string): string {
  return WORKER_COLORS[worker] ?? "var(--color-ink-soft)";
}

const DECISION_LABELS: Record<string, string> = {
  proceed: "Enough support for an explanation",
  clarify: "More information is needed",
  human_review: "A healthcare professional must review this",
};

export function decisionLabel(decision: string | null): string {
  if (!decision) return "No decision reported";
  return DECISION_LABELS[decision] ?? decision;
}

export type RowStatus = WorkerStatus | "waiting" | "needs_review";

const STATUS_LABELS: Record<RowStatus, string> = {
  waiting: "Waiting",
  needs_review: "Waiting for review",
  running: "Reviewing",
  succeeded: "Done",
  partial: "Partly done",
  failed: "Couldn't review",
  timed_out: "Took too long",
};

export function statusLabel(status: RowStatus): string {
  return STATUS_LABELS[status];
}

// What happened at one point on the care team strip.
export type MarkKind =
  | "started"
  | "completed"
  | "partial"
  | "failed"
  | "timed_out"
  | "searching"
  | "gap"
  | "recovery"
  | "verified"
  | "reviewed"
  | "checked"
  | "review_required";

const MARK_LABELS: Record<MarkKind, string> = {
  started: "Started",
  completed: "Done",
  partial: "Partly done",
  failed: "Couldn't review",
  timed_out: "Took too long",
  searching: "Searching for sources",
  gap: "Needs more sources",
  recovery: "Looking for more sources",
  verified: "Sources confirmed",
  reviewed: "Reviewed",
  checked: "Guidance checked",
  review_required: "Review needed",
};

export function markLabel(kind: MarkKind): string {
  return MARK_LABELS[kind];
}

// Heading above the strip, and the sentence announced to screen readers when the run changes.
const RUN_TEXT: Record<RunStatus, { heading: string; announcement: string }> = {
  idle: { heading: "Your care team", announcement: "No case is running." },
  running: { heading: "Your care team is reviewing", announcement: "Your care team is reviewing." },
  completed: { heading: "Your care team has finished", announcement: "The review has finished." },
  partial: { heading: "Your care team finished with gaps", announcement: "The review finished with gaps." },
  paused: {
    heading: "Your care team paused for review",
    announcement: "The review is paused. A healthcare professional needs to review this.",
  },
  failed: { heading: "The review could not be completed", announcement: "The review could not be completed." },
  cancelled: { heading: "The review was cancelled", announcement: "The review was cancelled." },
};

export function runText(status: RunStatus): { heading: string; announcement: string } {
  return RUN_TEXT[status];
}

const STEP_LABELS: Record<string, string> = {
  "intake.decomposed": "Organizing the request",
  "guidance.checked": "Guidance check",
};

// A model call is attributed to a worker, or to the event that triggered it.
export function stepLabel(actor: string): string {
  return WORKER_LABELS[actor] ?? STEP_LABELS[actor] ?? actor;
}

// "us.anthropic.claude-sonnet-4-6" becomes "claude-sonnet-4-6": the routing prefix adds noise.
export function shortModelName(model: string): string {
  return model.replace(/^(us|global)\.anthropic\./, "");
}
