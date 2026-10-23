import type { WorkflowEvent } from "../events/schema";
import type { Scenario } from "../mock/scenarios";
import visit1 from "./VP01-v1.json";
import visit2 from "./VP01-v2.json";
import visit3 from "./VP01-v3.json";

// Real runs of the backend, recorded by `python -m backend.record_runs` (real model output and a
// real guardrail check). They are replayed with their original timing, but long waits for the
// model are shortened so a rehearsal does not sit idle. Always shown as a recording, never as live.

interface RecordedFile {
  id: string;
  label: string;
  description: string;
  events: WorkflowEvent[];
}

const MIN_DELAY_MS = 150;
const MAX_DELAY_MS = 2500;

function toScenario(file: RecordedFile): Scenario {
  const events = file.events.map((event, index) => {
    const gap = index === 0 ? 0 : Date.parse(String(event.timestamp)) - Date.parse(String(file.events[index - 1].timestamp));
    const delayMs = index === 0 ? 0 : Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, Number.isFinite(gap) ? gap : MIN_DELAY_MS));
    return { delayMs, event };
  });
  return { id: file.id, label: file.label, description: file.description, events };
}

export const RECORDED: Scenario[] = [visit1, visit2, visit3].map((file) => toScenario(file as unknown as RecordedFile));
