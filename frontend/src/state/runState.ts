import { TERMINAL_EVENT_TYPES, parseWorkflowEvent } from "../events/schema";
import type { WorkflowEvent } from "../events/schema";
import {
  readAnswerSection,
  readDoctorDecision,
  readLimitations,
  readModelCall,
  readRecoveryQueries,
  readRedFlags,
  readReviewRequired,
  readRoutingQuestion,
  readTerminalInfo,
  readWorkerError,
} from "./payloadAdapters";
import type { AnswerSection, ModelCall, RecoveryQuery, RedFlag, WorkerError } from "./payloadAdapters";

// Everything the screen shows is a pure function of the events received so far:
//   state = buildRunState(events)
// Events are sorted by `sequence` and folded in order. Rebuilding from the full list on every
// event makes out-of-order arrival, duplicates after a reconnect, and replays all correct by
// construction. A run has tens of events, so the cost is negligible.

export type RunStatus = "idle" | "running" | "completed" | "partial" | "failed" | "cancelled" | "paused";
export type WorkerStatus = "running" | "succeeded" | "partial" | "failed" | "timed_out";
export type AnswerStatus = "not_started" | "generating" | "completed";
export type ViewMode = "patient" | "audit" | "operator";

export interface ModelCallRecord extends ModelCall {
  eventId: string;
  sequence: number;
  actor: string; // node / worker that made the call, or the event type as a fallback
}

export interface WorkerCard {
  worker: string;
  taskId: string | null;
  question: string | null;
  status: WorkerStatus;
  summary: string | null;
  limitations: string[];
  error: WorkerError | null;
  evidenceIds: string[];
  modelCalls: ModelCallRecord[];
  retrievalRound: number | null;
  startedSequence: number | null;
  finishedSequence: number | null;
}

export interface DoctorReview {
  decision: string | null;
  reason: string | null;
  summary: string;
}

export interface ReviewState {
  required: boolean;
  reason: string | null;
  flagIds: string[];
  resumable: boolean;
}

export interface RecoveryState {
  requested: boolean;
  granted: boolean;
  denied: boolean;
  completed: boolean;
  queries: RecoveryQuery[];
}

export interface Outcome {
  type: (typeof TERMINAL_EVENT_TYPES)[number];
  summary: string;
  detail: string | null; // payload.outcome, if provided
  limitations: string[];
  resumable: boolean;
}

export interface Rejected {
  reason: string;
  eventId: string | null;
  raw: unknown;
}

export interface RunState {
  runId: string | null;
  status: RunStatus;
  events: WorkflowEvent[]; // deduplicated, sorted by sequence: the timeline source
  workers: WorkerCard[]; // in order of first appearance
  doctor: DoctorReview | null;
  redFlags: RedFlag[]; // only ever grows: a later event cannot erase a flag
  review: ReviewState;
  recovery: RecoveryState;
  answer: { status: AnswerStatus; sections: AnswerSection[] };
  modelCalls: ModelCallRecord[]; // every model call seen, for the transparency view
  outcome: Outcome | null;
  rejected: Rejected[]; // messages refused, with the reason
}

const NON_WORKER_ACTORS = new Set(["orchestrator", "doctor_synthesis"]);

const STATUS_BY_TERMINAL: Record<Outcome["type"], RunStatus> = {
  "run.completed": "completed",
  "run.partial": "partial",
  "run.failed": "failed",
  "run.cancelled": "cancelled",
  "run.paused": "paused",
  "run.needs_human_review": "paused",
  "run.needs_clarification": "paused",
  "run.unsupported": "partial",
};

function isTerminalType(type: string): type is Outcome["type"] {
  return (TERMINAL_EVENT_TYPES as readonly string[]).includes(type);
}

// Which specialist worker an event is about, or null (orchestrator / doctor / run-level events).
export function workerOf(event: WorkflowEvent): string | null {
  const name = event.type === "routing.assigned" ? event.destination_worker : (event.node ?? event.source_worker);
  if (!name || NON_WORKER_ACTORS.has(name)) return null;
  return name;
}

export function buildRunState(events: WorkflowEvent[], rejected: Rejected[] = []): RunState {
  const sorted = [...events].sort((a, b) => a.sequence - b.sequence);
  const terminal = sorted.find((e) => isTerminalType(e.type));

  const cards = new Map<string, WorkerCard>();
  const redFlags = new Map<string, RedFlag>();
  const sections = new Map<string, AnswerSection>();
  const modelCalls: ModelCallRecord[] = [];
  let doctor: DoctorReview | null = null;
  let review: ReviewState = { required: false, reason: null, flagIds: [], resumable: false };
  const recovery: RecoveryState = { requested: false, granted: false, denied: false, completed: false, queries: [] };
  let answerStatus: AnswerStatus = "not_started";
  let outcome: Outcome | null = null;

  const card = (name: string): WorkerCard => {
    let existing = cards.get(name);
    if (!existing) {
      existing = {
        worker: name,
        taskId: null,
        question: null,
        status: "running",
        summary: null,
        limitations: [],
        error: null,
        evidenceIds: [],
        modelCalls: [],
        retrievalRound: null,
        startedSequence: null,
        finishedSequence: null,
      };
      cards.set(name, existing);
    }
    return existing;
  };

  for (const event of sorted) {
    // After the run's terminal event, later events stay in the timeline but cannot change the
    // result: a late message must not silently alter an already finalized response.
    if (terminal && event.sequence > terminal.sequence) continue;

    const payload = event.payload;
    const worker = workerOf(event);

    const call = readModelCall(payload);
    if (call) {
      const record: ModelCallRecord = {
        ...call,
        eventId: event.event_id,
        sequence: event.sequence,
        actor: event.node ?? event.source_worker ?? event.type,
      };
      modelCalls.push(record);
      if (worker) card(worker).modelCalls.push(record);
    }

    for (const flag of readRedFlags(payload)) {
      if (!redFlags.has(flag.id)) redFlags.set(flag.id, flag);
    }

    if (worker && event.task_id) card(worker).taskId = event.task_id;
    if (worker && event.retrieval_round != null) {
      const c = card(worker);
      c.retrievalRound = Math.max(c.retrievalRound ?? 0, event.retrieval_round);
    }

    switch (event.type) {
      case "routing.assigned":
        if (worker) card(worker).question = readRoutingQuestion(payload) ?? card(worker).question;
        break;

      case "worker.started":
        if (worker) {
          const c = card(worker);
          c.status = "running";
          c.startedSequence = event.sequence;
        }
        break;

      case "worker.completed":
        if (worker) {
          const c = card(worker);
          c.status = event.status === "partial" ? "partial" : "succeeded";
          c.summary = event.summary;
          c.limitations = readLimitations(payload);
          c.evidenceIds = event.evidence_ids;
          c.finishedSequence = event.sequence;
        }
        break;

      case "worker.failed":
      case "worker.timed_out":
        if (worker) {
          const c = card(worker);
          c.status = event.type === "worker.failed" ? "failed" : "timed_out";
          c.summary = event.summary;
          c.error = readWorkerError(payload);
          c.finishedSequence = event.sequence;
        }
        break;

      case "doctor.review_completed": {
        const decision = readDoctorDecision(payload);
        doctor = { decision: decision?.decision ?? null, reason: decision?.reason ?? null, summary: event.summary };
        break;
      }

      case "review.required": {
        const info = readReviewRequired(payload);
        review = { required: true, reason: event.summary, flagIds: info.flagIds, resumable: info.resumable };
        break;
      }

      case "recovery.requested":
        recovery.requested = true;
        break;
      case "recovery.granted":
        recovery.granted = true;
        break;
      case "recovery.denied":
        recovery.denied = true;
        break;
      case "recovery.queries_generated":
        recovery.queries = readRecoveryQueries(payload);
        break;
      case "recovery.completed":
        recovery.completed = true;
        break;

      case "answer.started":
        answerStatus = "generating";
        break;
      case "answer.section": {
        const section = readAnswerSection(payload, event.evidence_ids);
        if (section) sections.set(section.id, section);
        break;
      }
      case "answer.completed":
        answerStatus = "completed";
        break;

      default:
        if (isTerminalType(event.type) && !outcome) {
          const info = readTerminalInfo(payload);
          outcome = {
            type: event.type,
            summary: event.summary,
            detail: info.outcome,
            limitations: info.limitations,
            resumable: info.resumable,
          };
        }
    }
  }

  const status: RunStatus = sorted.length === 0 ? "idle" : outcome ? STATUS_BY_TERMINAL[outcome.type] : "running";

  return {
    runId: sorted[0]?.run_id ?? null,
    status,
    events: sorted,
    workers: [...cards.values()],
    doctor,
    redFlags: [...redFlags.values()],
    review,
    recovery,
    answer: { status: answerStatus, sections: [...sections.values()].sort((a, b) => a.order - b.order) },
    modelCalls,
    outcome,
    rejected,
  };
}

export function createInitialState(): RunState {
  return buildRunState([]);
}

// Add one event. Returns the SAME state object when nothing changes (e.g. a repeated event),
// which also lets React skip a re-render.
export function applyEvent(state: RunState, event: WorkflowEvent): RunState {
  if (state.runId !== null && event.run_id !== state.runId) {
    return withRejected(state, `event belongs to run ${event.run_id}, not ${state.runId}`, event.event_id, event);
  }

  const existing = state.events.find((e) => e.event_id === event.event_id);
  if (existing) {
    if (JSON.stringify(existing) === JSON.stringify(event)) return state;
    // Same id, different content is an integrity error, not an update (first one wins).
    return withRejected(state, `conflicting duplicate event_id ${event.event_id}`, event.event_id, event);
  }

  return buildRunState([...state.events, event], state.rejected);
}

// Entry point for raw messages from the stream or the replay player: validate, then apply.
// A malformed message is recorded in `rejected` and never throws.
export function ingestRaw(state: RunState, raw: unknown): RunState {
  const result = parseWorkflowEvent(raw);
  if (!result.ok) {
    const eventId =
      typeof raw === "object" && raw !== null && typeof (raw as { event_id?: unknown }).event_id === "string"
        ? (raw as { event_id: string }).event_id
        : null;
    return withRejected(state, result.error, eventId, raw);
  }
  return applyEvent(state, result.event);
}

function withRejected(state: RunState, reason: string, eventId: string | null, raw: unknown): RunState {
  return { ...state, rejected: [...state.rejected, { reason, eventId, raw }] };
}

// patient = what a patient or caregiver sees. audit adds the specialist and model detail.
// operator shows everything, including internal events.
export function visibleEvents(state: RunState, mode: ViewMode): WorkflowEvent[] {
  if (mode === "operator") return state.events;
  const allowed = mode === "patient" ? ["patient"] : ["patient", "demo_detail"];
  return state.events.filter((e) => allowed.includes(e.visibility));
}

// Sums only the values the backend reported. Unknown usage is skipped, not guessed.
export function modelCallTotals(state: RunState) {
  let inputTokens = 0;
  let outputTokens = 0;
  let durationMs = 0;
  for (const call of state.modelCalls) {
    inputTokens += call.inputTokens ?? 0;
    outputTokens += call.outputTokens ?? 0;
    durationMs += call.durationMs ?? 0;
  }
  return { calls: state.modelCalls.length, inputTokens, outputTokens, durationMs };
}
