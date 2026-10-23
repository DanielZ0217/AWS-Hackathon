import type { Scenario } from "../mock/scenarios";
import type { ConnectionStatus } from "../source/types";
import { buttonPrimary, buttonSecondary } from "./buttonStyles";

const SPEEDS = [1, 2, 4];

interface Props {
  scenarios: Pick<Scenario, "id" | "label">[];
  selectedId: string;
  description: string; // what the selected case demonstrates
  onSelect: (id: string) => void;
  status: ConnectionStatus;
  step: number;
  totalSteps: number;
  speed: number;
  onSpeed: (speed: number) => void;
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
}

export function CaseControls(p: Props) {
  const primary =
    p.status === "live"
      ? { label: "Pause", onClick: p.onPause }
      : p.status === "paused"
        ? { label: "Resume", onClick: p.onResume }
        : { label: p.status === "ended" ? "Run again" : "Run case", onClick: p.onRun };

  return (
    <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
      <div>
        <label htmlFor="case-select" className="block text-sm font-bold">
          Case
        </label>
        <select
          id="case-select"
          value={p.selectedId}
          onChange={(e) => p.onSelect(e.target.value)}
          className="mt-1 rounded-sm border border-ink bg-surface px-3 py-2"
        >
          {p.scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex gap-2">
        <button type="button" className={buttonPrimary} onClick={primary.onClick}>
          {primary.label}
        </button>
        <button type="button" className={buttonSecondary} onClick={p.onRestart} disabled={p.status === "idle"}>
          Restart
        </button>
      </div>

      <div role="group" aria-label="Replay speed" className="flex items-center gap-2">
        <span className="text-sm font-bold">Speed</span>
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={p.speed === s}
            onClick={() => p.onSpeed(s)}
            className={`rounded-sm border border-ink px-3 py-1 text-sm font-bold ${
              p.speed === s ? "bg-ink text-paper" : "bg-surface text-ink"
            }`}
          >
            {s}x
          </button>
        ))}
      </div>

      {p.status !== "idle" && (
        <p className="text-sm text-ink-soft">
          Step {p.step} of {p.totalSteps}
        </p>
      )}

      <p className="basis-full text-sm text-ink-soft">What this case shows: {p.description}</p>
    </div>
  );
}
