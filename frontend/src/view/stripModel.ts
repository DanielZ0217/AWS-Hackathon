import { TERMINAL_EVENT_TYPES } from "../events/schema";
import type { WorkflowEvent } from "../events/schema";
import { DOCTOR_ROW, markLabel } from "../labels";
import type { MarkKind, RowStatus } from "../labels";
import { readRedFlags } from "../state/payloadAdapters";
import { workerOf } from "../state/runState";
import type { RunState } from "../state/runState";

// Turns a RunState into the geometry of the care team strip. Pure, so it is tested without a
// browser; the SVG component only draws what this returns.
//
// Layout: one row per specialist, with the doctor row where everything converges. The
// horizontal axis is EVENT ORDER, not clock time: each event that appears on the strip takes the
// next column, so a burst of events never overlaps and there are no empty gaps.

export interface StripRow {
  id: string;
  status: RowStatus;
}

export interface StripMark {
  eventId: string;
  row: string;
  col: number;
  kind: MarkKind;
  label: string;
  flagged: boolean; // carries a red flag
}

// The span of a worker's activity, from its start to its finish (or to the latest column).
export interface StripBar {
  row: string;
  fromCol: number;
  toCol: number;
  open: boolean; // still in progress
}

// A finished worker passing its result to the doctor. A failed worker still reaches the
// doctor, as a "gap" so the missing analysis is visible rather than hidden.
export interface StripHandoff {
  fromRow: string;
  fromCol: number;
  toCol: number;
  kind: "result" | "gap";
}

export interface StripModel {
  rows: StripRow[];
  marks: StripMark[];
  bars: StripBar[];
  handoffs: StripHandoff[];
  columnCount: number;
  frozen: boolean; // a human must review before the run goes further
  alarmColumn: number | null; // column of the first red flag
}

const DOWNSTREAM_WORKERS = new Set(["nutrition", "physio"]);
const TERMINAL_MARKS = new Set<MarkKind>(["completed", "partial", "failed", "timed_out"]);

// Which strip row and mark (if any) an event produces. Most events produce none: they appear in
// the "How we got this" list instead, which keeps the strip readable.
function markFor(event: WorkflowEvent): { row: string; kind: MarkKind } | null {
  const worker = workerOf(event);
  switch (event.type) {
    case "worker.started":
      return worker ? { row: worker, kind: "started" } : null;
    case "worker.completed":
      return worker ? { row: worker, kind: event.status === "partial" ? "partial" : "completed" } : null;
    case "worker.failed":
      return worker ? { row: worker, kind: "failed" } : null;
    case "worker.timed_out":
      return worker ? { row: worker, kind: "timed_out" } : null;
    case "retrieval.started":
      return worker ? { row: worker, kind: "searching" } : null;
    case "evaluation.insufficient":
      return worker ? { row: worker, kind: "gap" } : null;
    case "recovery.granted": {
      // This event is sent by the orchestrator, so the affected worker is its destination.
      const target = event.destination_worker;
      return target ? { row: target, kind: "recovery" } : null;
    }
    case "evaluation.passed":
      return worker ? { row: worker, kind: "verified" } : null;
    case "doctor.review_completed":
      return { row: DOCTOR_ROW, kind: "reviewed" };
    case "guidance.checked":
      return { row: DOCTOR_ROW, kind: "checked" };
    case "review.required":
      return { row: DOCTOR_ROW, kind: "review_required" };
    default:
      return null;
  }
}

export function buildStripModel(state: RunState): StripModel {
  const terminal = state.events.find((e) => (TERMINAL_EVENT_TYPES as readonly string[]).includes(e.type));

  // Rows: diagnostic workers in order of appearance, then the doctor, then downstream workers.
  const workerRows: StripRow[] = state.workers
    .filter((w) => !DOWNSTREAM_WORKERS.has(w.worker))
    .map((w) => ({ id: w.worker, status: w.status }));
  const downstreamRows: StripRow[] = state.workers
    .filter((w) => DOWNSTREAM_WORKERS.has(w.worker))
    .map((w) => ({ id: w.worker, status: w.status }));
  const showDoctor = state.workers.length > 0 || state.doctor !== null;
  // While a human review is pending, the doctor row must not read "Done".
  const doctorStatus: RowStatus = state.review.required ? "needs_review" : state.doctor ? "succeeded" : "waiting";
  const doctorRow: StripRow[] = showDoctor ? [{ id: DOCTOR_ROW, status: doctorStatus }] : [];
  const rows = [...workerRows, ...doctorRow, ...downstreamRows];
  const rowIds = new Set(rows.map((r) => r.id));

  // Marks: each strip-relevant event takes the next column. Events after the run's terminal
  // event are left out, matching the frozen result in RunState.
  const marks: StripMark[] = [];
  for (const event of state.events) {
    if (terminal && event.sequence > terminal.sequence) continue;
    const mark = markFor(event);
    if (!mark || !rowIds.has(mark.row)) continue;
    marks.push({
      eventId: event.event_id,
      row: mark.row,
      col: marks.length,
      kind: mark.kind,
      label: markLabel(mark.kind),
      flagged: mark.kind === "review_required" || readRedFlags(event.payload).length > 0,
    });
  }

  const headColumn = marks.length - 1;

  // Bars: from each worker's start to its finish, or to the latest column while still running.
  const bars: StripBar[] = [];
  for (const row of workerRows) {
    const rowMarks = marks.filter((m) => m.row === row.id);
    const started = rowMarks.find((m) => m.kind === "started");
    if (!started) continue;
    const finished = rowMarks.find((m) => TERMINAL_MARKS.has(m.kind) && m.col > started.col);
    bars.push(
      finished
        ? { row: row.id, fromCol: started.col, toCol: finished.col, open: false }
        : { row: row.id, fromCol: started.col, toCol: Math.max(headColumn, started.col), open: true },
    );
  }

  // Handoffs: each finished worker to the doctor's review mark, once the doctor has reviewed.
  const handoffs: StripHandoff[] = [];
  const reviewed = marks.find((m) => m.row === DOCTOR_ROW && m.kind === "reviewed");
  if (reviewed) {
    for (const row of workerRows) {
      const finished = marks.find((m) => m.row === row.id && TERMINAL_MARKS.has(m.kind) && m.col < reviewed.col);
      if (!finished) continue;
      const failed = finished.kind === "failed" || finished.kind === "timed_out";
      handoffs.push({ fromRow: row.id, fromCol: finished.col, toCol: reviewed.col, kind: failed ? "gap" : "result" });
    }
  }

  return {
    rows,
    marks,
    bars,
    handoffs,
    columnCount: marks.length,
    frozen: state.review.required || state.status === "paused",
    alarmColumn: marks.find((m) => m.flagged)?.col ?? null,
  };
}
