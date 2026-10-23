import type { ConnectionStatus, SourceMode } from "../source/types";
import { buttonPrimary, buttonSecondary } from "./buttonStyles";

interface CaseOption {
  id: string;
  label: string;
}

interface Props {
  mode: SourceMode;
  scenarios: CaseOption[];
  selectedId: string;
  description: string; // what the selected case demonstrates
  onSelect: (id: string) => void;
  status: ConnectionStatus;
  step: number;
  totalSteps: number; // 0 when unknown (live)
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
}

export function CaseControls(p: Props) {
  const live = p.mode === "live";
  const running = p.status === "live" || p.status === "connecting";

  // A live run cannot be paused or sped up, so those controls only exist for the replay.
  const primary = live
    ? { label: running ? "Running" : p.status === "ended" ? "Run again" : "Run case", onClick: p.onRun, disabled: running }
    : p.status === "live"
      ? { label: "Pause", onClick: p.onPause, disabled: false }
      : p.status === "paused"
        ? { label: "Resume", onClick: p.onResume, disabled: false }
        : { label: p.status === "ended" ? "Run again" : "Run case", onClick: p.onRun, disabled: false };

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
        <button type="button" className={buttonPrimary} onClick={primary.onClick} disabled={primary.disabled}>
          {primary.label}
        </button>
        {!live && (
          <button type="button" className={buttonSecondary} onClick={p.onRestart} disabled={p.status === "idle"}>
            Restart
          </button>
        )}
      </div>

      {p.status !== "idle" && p.status !== "error" && (
        <p className="text-sm text-ink-soft">{p.totalSteps > 0 ? `Step ${p.step} of ${p.totalSteps}` : `Step ${p.step}`}</p>
      )}

      {p.status === "error" && (
        <p role="alert" className="basis-full font-bold">
          Couldn&apos;t reach the backend. Check that it is running, then reload the page.
        </p>
      )}

      <p className="basis-full text-sm text-ink-soft">What this case shows: {p.description}</p>
    </div>
  );
}
