import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CareTeamStrip } from "./components/CareTeamStrip";
import { CaseControls } from "./components/CaseControls";
import { DisclaimerBanner } from "./components/DisclaimerBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HowWeGotThis } from "./components/HowWeGotThis";
import { Summary } from "./components/Summary";
import { runText } from "./labels";
import { RECORDED } from "./recorded/recorded";
import { fetchPresets } from "./source/api";
import type { PresetSummary } from "./source/api";
import { LiveSource } from "./source/liveSource";
import { ReplaySource } from "./source/replaySource";
import type { EventSourceLike, SourceMode } from "./source/types";
import { useRunStream } from "./source/useRunStream";
import { buildStripModel } from "./view/stripModel";
import { buildSummaryModel } from "./view/summaryModel";

export default function App() {
  const [mode, setMode] = useState<SourceMode>("replay");
  const [presets, setPresets] = useState<PresetSummary[] | null>(null);
  const [presetId, setPresetId] = useState("");
  const [scenarioId, setScenarioId] = useState(RECORDED[0].id);
  const [speed, setSpeed] = useState(1);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);
  const detailsButton = useRef<HTMLButtonElement>(null);

  // Ask the backend for its patients once. If it answers, start on the live source; if not,
  // stay on the recorded replay so the screen never opens broken.
  useEffect(() => {
    let cancelled = false;
    void fetchPresets().then((found) => {
      if (cancelled || !found || found.length === 0) return;
      setPresets(found);
      setPresetId(found[0].id);
      setMode("live");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const scenario = RECORDED.find((s) => s.id === scenarioId) ?? RECORDED[0];
  const preset = presets?.find((p) => p.id === presetId);

  // One source per selection. Changing speed re-times the same replay instead of recreating it.
  const replay = useMemo(() => new ReplaySource(scenario), [scenario]);
  const live = useMemo(() => new LiveSource(presetId), [presetId]);
  useEffect(() => {
    replay.setSpeed(speed);
  }, [replay, speed]);
  const source: EventSourceLike = mode === "live" ? live : replay;

  const { run, status } = useRunStream(source);
  const strip = useMemo(() => buildStripModel(run), [run]);
  const summary = useMemo(() => buildSummaryModel(run), [run]);
  const text = runText(run.status);

  const closeDetails = useCallback(() => {
    setDetailsOpen(false);
    detailsButton.current?.focus();
  }, []);

  const changeMode = (next: SourceMode) => {
    setMode(next);
    setDetailsOpen(false);
  };

  const selectCase = (id: string) => {
    if (mode === "live") setPresetId(id);
    else setScenarioId(id);
    setDetailsOpen(false);
  };

  const options = mode === "live" ? (presets ?? []) : RECORDED;

  return (
    <div className="min-h-svh bg-paper">
      <DisclaimerBanner replay={source.kind === "replay"} />

      {/* The safety stop, visible at the top of the screen. Hidden from screen readers because
          the alert in the summary already announces it. */}
      {run.review.required && (
        <div aria-hidden="true" className="bg-alarm px-4 py-2 text-center font-bold text-paper">
          Paused for review. A healthcare professional needs to look at this before any guidance is shown.
        </div>
      )}

      <main className="mx-auto max-w-6xl space-y-8 px-4 py-6">
        <header>
          <h1 className="text-2xl font-bold">Care team review</h1>
          <p className="mt-1 max-w-[62ch] text-ink-soft">
            Follow how a team of specialists looks at one patient&apos;s results, then read a summary in plain language.
          </p>
        </header>

        <CaseControls
          mode={mode}
          liveAvailable={presets !== null}
          onModeChange={changeMode}
          scenarios={options}
          selectedId={mode === "live" ? presetId : scenarioId}
          description={mode === "live" ? (preset?.description ?? "") : scenario.description}
          onSelect={selectCase}
          status={status}
          step={run.events.length}
          totalSteps={mode === "replay" ? scenario.events.length : 0}
          speed={speed}
          onSpeed={setSpeed}
          onRun={() => source.start()}
          onPause={() => replay.pause()}
          onResume={() => replay.resume()}
          onRestart={() => replay.restart()}
        />

        {/* Read out by screen readers when the run changes. */}
        <p role="status" className="sr-only">
          {text.announcement}
        </p>

        <section aria-labelledby="team-title">
          <h2 id="team-title" className="mb-2 text-xl font-bold">
            {text.heading}
          </h2>
          <ErrorBoundary>
            <CareTeamStrip model={strip} />
          </ErrorBoundary>
        </section>

        <section aria-labelledby="summary-title">
          <ErrorBoundary>
            <Summary
              run={run}
              summary={summary}
              detailsOpen={detailsOpen}
              onToggleDetails={() => setDetailsOpen((open) => !open)}
              detailsButtonRef={detailsButton}
            />
          </ErrorBoundary>
        </section>
      </main>

      <ErrorBoundary>
        <HowWeGotThis
          run={run}
          strip={strip}
          open={detailsOpen}
          onClose={closeDetails}
          showTechnical={showTechnical}
          onToggleTechnical={setShowTechnical}
        />
      </ErrorBoundary>
    </div>
  );
}
