import { workerLabel } from "../labels";
import { readEvidenceWorker } from "../state/payloadAdapters";
import type { RunState } from "../state/runState";

// What the patient-facing summary should show for a run. Pure, so the wording and the states
// are tested without a browser.

export type SummaryStage =
  | "idle" // nothing has happened yet
  | "working" // events are arriving but no sections yet
  | "review" // a healthcare professional must review before guidance is shown
  | "ready" // sections are available
  | "empty"; // the run ended without producing a summary

export interface SummarySection {
  id: string;
  title: string;
  text: string;
  basedOn: string[]; // plain names of the specialists whose findings the section rests on
}

export interface SummaryModel {
  stage: SummaryStage;
  sections: SummarySection[];
  gaps: string[]; // parts that could not be reviewed
  limitations: string[]; // what the summary cannot tell the reader
}

export function buildSummaryModel(run: RunState): SummaryModel {
  const sections: SummarySection[] = run.answer.sections.map((s) => {
    const workers = new Set<string>();
    for (const id of s.evidenceIds) {
      const worker = readEvidenceWorker(id);
      if (worker) workers.add(worker);
    }
    return { id: s.id, title: s.title, text: s.text, basedOn: [...workers].map(workerLabel) };
  });

  const gaps = run.workers
    .filter((w) => w.status === "failed" || w.status === "timed_out")
    .map((w) => `${workerLabel(w.worker)} couldn't be reviewed. ${w.error?.nextAction ?? "A clinician should re-evaluate it."}`);

  let stage: SummaryStage;
  if (run.events.length === 0) stage = "idle";
  else if (run.review.required) stage = "review";
  else if (sections.length > 0) stage = "ready";
  else if (run.outcome) stage = "empty";
  else stage = "working";

  return { stage, sections, gaps, limitations: run.outcome?.limitations ?? [] };
}
