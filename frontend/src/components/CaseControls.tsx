import type { ConnectionStatus, SourceMode } from "../source/types";
import { buttonPrimary, buttonSecondary } from "./buttonStyles";

const SPEEDS = [1, 2, 4];

interface CaseOption {
  id: string;
  label: string;
}

interface Props {
  mode: SourceMode;
  liveAvailable: boolean; // false when the backend did not answer
  onModeChange: (mode: SourceMode) => void;
  scenarios: CaseOption[];
  selectedId: string;
  description: string; // what the selected case demonstrates
  onSelect: (id: string) => void;
  status: ConnectionStatus;
  step: number;
  totalSteps: number; // 0 when unknown (live)
  speed: number;
  onSpeed: (speed: number) => void;
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
      <div role="group" aria-label="Where the events come from">
        <span className="block text-sm font-bold">Source</span>
        <div className="mt-1 flex">
          {(["live", "replay"] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={p.mode === m}
              disabled={m === "live" && !p.liveAvailable}
              onClick={() => p.onModeChange(m)}
              title={m === "live" && !p.liveAvailable ? "The backend did not respond" : undefined}
              className={`border border-ink px-3 py-2 text-sm font-bold first:rounded-l-sm last:rounded-r-sm disabled:cursor-not-allowed disabled:opacity-40 ${
                p.mode === m ? "bg-ink text-paper" : "bg-surface text-ink"
              }`}
            >
              {m === "live" ? "Live backend" : "Recorded replay"}
            </button>
          ))}
        </div>
      </div>

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

      {!live && (
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
      )}

      {p.status !== "idle" && p.status !== "error" && (
        <p className="text-sm text-ink-soft">{p.totalSteps > 0 ? `Step ${p.step} of ${p.totalSteps}` : `Step ${p.step}`}</p>
      )}

      {p.status === "error" && (
        <p role="alert" className="basis-full font-bold">
          Couldn&apos;t reach the backend. Check that it is running, or switch to the recorded replay.
        </p>
      )}

      <p className="basis-full text-sm text-ink-soft">What this case shows: {p.description}</p>
    </div>
  );
}
