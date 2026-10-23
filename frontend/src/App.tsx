import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CareTeamStrip } from "./components/CareTeamStrip";
import { CaseControls } from "./components/CaseControls";
import { DisclaimerBanner } from "./components/DisclaimerBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HowWeGotThis } from "./components/HowWeGotThis";
import { Summary } from "./components/Summary";
import { runText } from "./labels";
import { SCENARIOS, getScenario } from "./mock/scenarios";
import { ReplaySource } from "./source/replaySource";
import { useRunStream } from "./source/useRunStream";
import { buildStripModel } from "./view/stripModel";
import { buildSummaryModel } from "./view/summaryModel";

export default function App() {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id);
  const [speed, setSpeed] = useState(1);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);
  const detailsButton = useRef<HTMLButtonElement>(null);

  const scenario = getScenario(scenarioId) ?? SCENARIOS[0];
  // One source per case. Changing speed re-times the same source instead of recreating it.
  const source = useMemo(() => new ReplaySource(scenario), [scenario]);
  useEffect(() => {
    source.setSpeed(speed);
  }, [source, speed]);

  const { run, status } = useRunStream(source);
  const strip = useMemo(() => buildStripModel(run), [run]);
  const summary = useMemo(() => buildSummaryModel(run), [run]);
  const text = runText(run.status);

  const closeDetails = useCallback(() => {
    setDetailsOpen(false);
    detailsButton.current?.focus();
  }, []);

  const selectScenario = (id: string) => {
    setScenarioId(id);
    setDetailsOpen(false);
  };

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
          scenarios={SCENARIOS}
          selectedId={scenarioId}
          description={scenario.description}
          onSelect={selectScenario}
          status={status}
          step={run.events.length}
          totalSteps={scenario.events.length}
          speed={speed}
          onSpeed={setSpeed}
          onRun={() => source.start()}
          onPause={() => source.pause()}
          onResume={() => source.resume()}
          onRestart={() => source.restart()}
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
