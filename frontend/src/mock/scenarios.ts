import type { Visibility, WorkflowEvent } from "../events/schema";

// MOCK DATA for UI development. Payload shapes are ASSUMPTIONS: the backend has not defined
// them yet. All clinical wording is generic placeholder text, not medical content.

export type ScriptedEvent = { delayMs: number; event: WorkflowEvent };

export interface Scenario {
  id: string;
  label: string;
  description: string;
  events: ScriptedEvent[];
}

// What a scenario author writes. buildScenario fills in the rest of the envelope.
interface Step {
  delayMs: number; // wait this long (ms) after the previous event before emitting
  type: string;
  summary: string;
  visibility?: Visibility; // defaults to demo_detail
  node?: string;
  task_id?: string;
  need_ids?: string[];
  status?: string;
  source_worker?: string;
  destination_worker?: string;
  evidence_ids?: string[];
  retrieval_round?: number;
  payload?: Record<string, unknown>;
}

const START_TIME = Date.parse("2026-10-23T14:00:00Z");

function buildScenario(id: string, label: string, description: string, steps: Step[]): Scenario {
  const runId = `run-${id}`;
  let elapsedMs = 0;
  const events = steps.map((step, index): ScriptedEvent => {
    elapsedMs += step.delayMs;
    const event: WorkflowEvent = {
      event_id: `${runId}-evt-${String(index + 1).padStart(3, "0")}`,
      run_id: runId,
      sequence: index + 1,
      timestamp: new Date(START_TIME + elapsedMs).toISOString(),
      type: step.type,
      summary: step.summary,
      visibility: step.visibility ?? "demo_detail",
      schema_version: "mock-0",
      trace_id: `trace-${id}`,
      node: step.node,
      task_id: step.task_id,
      need_ids: step.need_ids ?? [],
      status: step.status,
      source_worker: step.source_worker,
      destination_worker: step.destination_worker,
      artifact_ids: [],
      evidence_ids: step.evidence_ids ?? [],
      retrieval_round: step.retrieval_round,
      payload: step.payload ?? {},
    };
    return { delayMs: step.delayMs, event };
  });
  return { id, label, description, events };
}

// ---------------------------------------------------------------------------
// Shared building blocks
// ---------------------------------------------------------------------------

const MOCK_MODEL = "us.anthropic.claude-sonnet-4-6";

// ASSUMED shape for the "show every model call" detail drawer.
function modelCall(inputTokens: number, outputTokens: number, durationMs: number) {
  return { model: MOCK_MODEL, input_tokens: inputTokens, output_tokens: outputTokens, duration_ms: durationMs };
}

const WORKERS = {
  lab: { task: "task-lab", need: "need-1", question: "What do the lab results show?" },
  radiology: { task: "task-radiology", need: "need-2", question: "What does the chest image show?" },
  ecg: { task: "task-ecg", need: "need-3", question: "What does the ECG show?" },
} as const;

type DiagnosticWorker = keyof typeof WORKERS;

// Plain names used in event summaries, which the screens show as written.
const PLAIN = { lab: "Lab results", radiology: "Chest image", ecg: "Heart rhythm" } as const;

const ALL_NEEDS = ["need-1", "need-2", "need-3", "need-4"];

// run.started through the three parallel worker.started events.
function opening(): Step[] {
  const workers = Object.keys(WORKERS) as DiagnosticWorker[];
  return [
    {
      delayMs: 0,
      type: "run.started",
      visibility: "patient",
      summary: "Run started for synthetic demo patient (placeholder)",
      payload: { preset_id: "demo-placeholder" },
    },
    { delayMs: 400, type: "intake.started", summary: "Organizing the request" },
    {
      delayMs: 900,
      type: "intake.decomposed",
      summary: "Organized request into 4 questions",
      need_ids: ALL_NEEDS,
      payload: {
        needs: [
          ...workers.map((w) => ({ need_id: WORKERS[w].need, question: WORKERS[w].question })),
          { need_id: "need-4", question: "Explain the combined picture in plain language." },
        ],
        model_call: modelCall(1180, 340, 820),
      },
    },
    ...workers.map(
      (w, i): Step => ({
        delayMs: i === 0 ? 300 : 120,
        type: "routing.assigned",
        summary: `${WORKERS[w].question} Assigned to ${PLAIN[w]}.`,
        task_id: WORKERS[w].task,
        need_ids: [WORKERS[w].need],
        source_worker: "orchestrator",
        destination_worker: w,
        payload: { question: WORKERS[w].question, reason: `The need concerns the supplied ${w} evidence.` },
      }),
    ),
    ...workers.map(
      (w, i): Step => ({
        delayMs: i === 0 ? 250 : 100,
        type: "worker.started",
        summary: `${PLAIN[w]}: review started`,
        node: w,
        task_id: WORKERS[w].task,
        need_ids: [WORKERS[w].need],
        source_worker: "orchestrator",
        destination_worker: w,
        status: "running",
      }),
    ),
  ];
}

function workerCompleted(
  worker: DiagnosticWorker,
  delayMs: number,
  summary: string,
  extraPayload: Record<string, unknown> = {},
): Step {
  return {
    delayMs,
    type: "worker.completed",
    summary,
    node: worker,
    task_id: WORKERS[worker].task,
    need_ids: [WORKERS[worker].need],
    source_worker: worker,
    destination_worker: "doctor_synthesis",
    status: "succeeded",
    evidence_ids: [`ev-${worker}-1`],
    payload: {
      limitations: ["Placeholder finding for UI development."],
      model_call: modelCall(2100, 520, 1400),
      ...extraPayload,
    },
  };
}

function doctorReview(delayMs: number, decision: string, summary: string, reason: string): Step {
  return {
    delayMs,
    type: "doctor.review_completed",
    summary,
    node: "doctor_synthesis",
    source_worker: "doctor_synthesis",
    payload: { decision, reason, model_call: modelCall(3400, 610, 1900) },
  };
}

function guidanceSteps(): Step[] {
  return [
    {
      delayMs: 500,
      type: "guidance.started",
      summary: "Food and movement discussion points are being prepared",
      source_worker: "doctor_synthesis",
    },
    {
      delayMs: 1400,
      type: "guidance.checked",
      summary: "Guidance check passed",
      payload: { passed: true, model_call: modelCall(1900, 260, 900) },
    },
  ];
}

interface SectionInput {
  title: string;
  text: string;
  evidenceIds?: string[];
}

// answer.started, one answer.section per entry, then answer.completed. All patient-visible.
function answerSteps(sections: SectionInput[]): Step[] {
  return [
    { delayMs: 500, type: "answer.started", visibility: "patient", summary: "Preparing your summary" },
    ...sections.map(
      (s, i): Step => ({
        delayMs: 700,
        type: "answer.section",
        visibility: "patient",
        summary: `Section ready: ${s.title}`,
        evidence_ids: s.evidenceIds ?? [],
        payload: { section_id: `section-${i + 1}`, order: i + 1, title: s.title, text: s.text, rendering: "model" },
      }),
    ),
    { delayMs: 400, type: "answer.completed", visibility: "patient", summary: "Summary ready" },
  ];
}

const PLACEHOLDER = "(Placeholder text for UI development.)";

const REVIEWED_SECTION: SectionInput = {
  title: "What was reviewed",
  text: `Lab results, a chest image and an ECG for a synthetic demo patient were each reviewed by a separate specialist. ${PLACEHOLDER}`,
  evidenceIds: ["ev-lab-1", "ev-radiology-1", "ev-ecg-1"],
};

const QUESTIONS_SECTION: SectionInput = {
  title: "Questions to ask your doctor",
  text: `Bring these results to a healthcare professional and ask what they mean for you. This tool is a prototype and not medical advice. ${PLACEHOLDER}`,
};

// ---------------------------------------------------------------------------
// The four scenarios
// ---------------------------------------------------------------------------

const clean = buildScenario(
  "clean",
  "Standard case",
  "Three specialists run in parallel, the doctor synthesizes, and a patient summary is produced.",
  [
    ...opening(),
    workerCompleted("lab", 1800, "Lab results: review done"),
    workerCompleted("ecg", 700, "Heart rhythm: review done"),
    workerCompleted("radiology", 900, "Chest image: review done"),
    doctorReview(1500, "proceed", "Doctor: enough support for a qualified explanation", "All three specialists returned usable findings."),
    ...guidanceSteps(),
    ...answerSteps([
      REVIEWED_SECTION,
      {
        title: "What the findings may mean",
        text: `The specialists found items worth discussing with a clinician. Nothing here is a diagnosis. ${PLACEHOLDER}`,
        evidenceIds: ["ev-lab-1", "ev-ecg-1"],
      },
      {
        title: "Everyday habits to discuss",
        text: `Nutrition and movement discussion points to review with your care team before acting on them. ${PLACEHOLDER}`,
      },
      QUESTIONS_SECTION,
    ]),
    {
      delayMs: 300,
      type: "run.completed",
      visibility: "patient",
      summary: "Run completed with stated limitations",
      payload: { outcome: "completed", limitations: ["Prototype output. Not clinical clearance."] },
    },
  ],
);

const redFlag = buildScenario(
  "red-flag",
  "Red-flag safety stop",
  "A specialist reports a critical value. Care guidance is paused and a human must review.",
  [
    ...opening(),
    workerCompleted("lab", 1600, "Lab results: review done"),
    workerCompleted("ecg", 600, "Heart rhythm: review done, with a red flag", {
      red_flags: [
        {
          flag_id: "flag-001",
          description: "Critical value flagged (placeholder)",
          supporting_observation_ids: ["obs-ecg-1"],
          requires_human_review: true,
        },
      ],
    }),
    {
      delayMs: 400,
      type: "review.required",
      visibility: "patient",
      summary: "A critical finding needs review by a healthcare professional before any guidance is given",
      source_worker: "orchestrator",
      payload: { flag_ids: ["flag-001"], resumable: true },
    },
    workerCompleted("radiology", 700, "Chest image: review done (kept; the run stays paused)"),
    doctorReview(1200, "human_review", "Doctor: human review required", "A red flag is unresolved. No guidance will be produced."),
    {
      delayMs: 400,
      type: "run.paused",
      visibility: "patient",
      summary: "Paused for human review",
      payload: { outcome: "needs_human_review", resumable: true, flag_ids: ["flag-001"] },
    },
  ],
);

const workerFailure = buildScenario(
  "worker-failure",
  "Missing analysis",
  "The radiology worker fails. The run continues, states the gap, and asks for clinical re-evaluation.",
  [
    ...opening(),
    workerCompleted("lab", 1700, "Lab results: review done"),
    workerCompleted("ecg", 700, "Heart rhythm: review done"),
    {
      delayMs: 900,
      type: "worker.failed",
      summary: "Chest image: couldn't be reviewed",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      need_ids: [WORKERS.radiology.need],
      source_worker: "radiology",
      destination_worker: "doctor_synthesis",
      status: "failed",
      payload: {
        error_category: "analysis_unavailable",
        limitation: "Chest image could not be analyzed.",
        next_action: "Clinical re-evaluation requested.",
      },
    },
    doctorReview(1300, "clarify", "Doctor: partial picture, cannot cover the chest image", "One specialist failed. The summary must state the gap."),
    ...answerSteps([
      {
        title: "What was reviewed",
        text: `Lab results and an ECG were reviewed. ${PLACEHOLDER}`,
        evidenceIds: ["ev-lab-1", "ev-ecg-1"],
      },
      {
        title: "What we could not review",
        text: `The chest image could not be analyzed, so this summary does not cover it. Please ask a clinician to re-evaluate. ${PLACEHOLDER}`,
      },
      QUESTIONS_SECTION,
    ]),
    {
      delayMs: 300,
      type: "run.partial",
      visibility: "patient",
      summary: "Run finished with a partial result",
      payload: { outcome: "partial", limitations: ["The chest image could not be analyzed."] },
    },
  ],
);

// Labeled retrieval-gap fixture, as Layer 5 requires for demonstrating recovery.
const recovery = buildScenario(
  "recovery",
  "Evidence recovery",
  "Reference support is incomplete, so the one allowed recovery round runs and the check then passes.",
  [
    ...opening(),
    workerCompleted("lab", 1500, "Lab results: review done"),
    workerCompleted("ecg", 600, "Heart rhythm: review done"),
    {
      delayMs: 500,
      type: "retrieval.started",
      summary: "Chest image: searching reference material",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      retrieval_round: 1,
      payload: { method: "hybrid", corpus_version: "mock-corpus-0" },
    },
    {
      delayMs: 900,
      type: "retrieval.completed",
      summary: "Chest image: 12 possible sources found",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      retrieval_round: 1,
      payload: { candidate_count: 12 },
    },
    {
      delayMs: 500,
      type: "rerank.completed",
      summary: "Chest image: 3 sources selected",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      retrieval_round: 1,
      payload: { selected_count: 3 },
    },
    {
      delayMs: 400,
      type: "evaluation.started",
      summary: "Chest image: checking whether the sources support the findings",
      node: "radiology",
      task_id: WORKERS.radiology.task,
    },
    {
      delayMs: 800,
      type: "evaluation.insufficient",
      summary: "Chest image: sources are incomplete for one finding",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      payload: { missing: "Reference support for one claim" },
    },
    {
      delayMs: 300,
      type: "recovery.requested",
      summary: "Chest image: asked for one more round of sources",
      node: "radiology",
      task_id: WORKERS.radiology.task,
    },
    {
      delayMs: 300,
      type: "recovery.granted",
      summary: "One more round of source searching approved",
      source_worker: "orchestrator",
      destination_worker: "radiology",
      payload: { remaining_budget: 0 },
    },
    {
      delayMs: 900,
      type: "recovery.queries_generated",
      summary: "Prepared 3 follow-up searches (one is a search aid, not evidence)",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      payload: {
        queries: [
          { kind: "paraphrase", text: "Placeholder paraphrased query" },
          { kind: "step_back", text: "Placeholder broader question" },
          { kind: "hyde", label: "generated_search_aid", text: "Placeholder reference-style paragraph" },
        ],
        model_call: modelCall(900, 210, 700),
      },
    },
    {
      delayMs: 1000,
      type: "retrieval.completed",
      summary: "Chest image: 9 more possible sources found",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      retrieval_round: 2,
      payload: { candidate_count: 9 },
    },
    {
      delayMs: 500,
      type: "rerank.completed",
      summary: "Chest image: 4 sources selected",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      retrieval_round: 2,
      payload: { selected_count: 4 },
    },
    {
      delayMs: 300,
      type: "recovery.completed",
      summary: "Extra source search finished",
      node: "radiology",
      task_id: WORKERS.radiology.task,
    },
    {
      delayMs: 600,
      type: "evaluation.passed",
      summary: "Chest image: sources now support the findings",
      node: "radiology",
      task_id: WORKERS.radiology.task,
      payload: { scope_note: "Supports the explanation only. Not clinical clearance." },
    },
    workerCompleted("radiology", 400, "Chest image: review done after extra sources"),
    doctorReview(1400, "proceed", "Doctor: enough support for a qualified explanation", "Gap closed by the recovery round."),
    ...guidanceSteps(),
    ...answerSteps([REVIEWED_SECTION, QUESTIONS_SECTION]),
    {
      delayMs: 300,
      type: "run.completed",
      visibility: "patient",
      summary: "Run completed with stated limitations",
      payload: { outcome: "completed", limitations: ["Prototype output. Not clinical clearance."] },
    },
  ],
);

export const SCENARIOS: Scenario[] = [clean, redFlag, workerFailure, recovery];

export function getScenario(id: string): Scenario | undefined {
  return SCENARIOS.find((s) => s.id === id);
}
