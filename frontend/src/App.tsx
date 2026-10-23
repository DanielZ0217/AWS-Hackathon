import { useCallback, useMemo, useRef, useState } from "react";
import { CareTeamStrip } from "./components/CareTeamStrip";
import { DisclaimerBanner } from "./components/DisclaimerBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HowWeGotThis } from "./components/HowWeGotThis";
import { IntakeForm } from "./components/IntakeForm";
import { Summary } from "./components/Summary";
import { runText } from "./labels";
import { LiveSource } from "./source/liveSource";
import type { RunSubmission } from "./source/liveSource";
import { useRunStream } from "./source/useRunStream";
import { buildStripModel } from "./view/stripModel";
import { buildSummaryModel } from "./view/summaryModel";

export default function App() {
  const source = useMemo(() => new LiveSource(), []);
  const { run, status } = useRunStream(source);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);
  const detailsButton = useRef<HTMLButtonElement>(null);
  const strip = useMemo(() => buildStripModel(run), [run]);
  const summary = useMemo(() => buildSummaryModel(run), [run]);
  const text = runText(run.status);

  const closeDetails = useCallback(() => {
    setDetailsOpen(false);
    detailsButton.current?.focus();
  }, []);

  const start = (submission: RunSubmission) => {
    setDetailsOpen(false);
    source.startWith(submission);
  };

  return (
    <div className="min-h-svh bg-paper">
      <DisclaimerBanner />
      {run.review.required && (
        <div role="alert" className="bg-alarm px-4 py-2 text-center font-bold text-paper">
          Paused for review. A healthcare professional needs to look at this before any guidance is shown.
        </div>
      )}

      <main className="mx-auto max-w-6xl space-y-8 px-4 py-6">
        <header>
          <h1 className="text-2xl font-bold">Care team review</h1>
          <p className="mt-1 max-w-[68ch] text-ink-soft">
            Ask a question and add a lab report, X-ray, or ECG image. The care team streams each review step as it completes.
          </p>
        </header>

        <IntakeForm status={status} onSubmit={start} />

        <p role="status" className="sr-only">{text.announcement}</p>

        <section aria-labelledby="team-title">
          <h2 id="team-title" className="mb-2 text-xl font-bold">{text.heading}</h2>
          <ErrorBoundary><CareTeamStrip model={strip} /></ErrorBoundary>
        </section>

        <section aria-labelledby="summary-title">
          <ErrorBoundary>
            <Summary run={run} summary={summary} detailsOpen={detailsOpen}
              onToggleDetails={() => setDetailsOpen((open) => !open)} detailsButtonRef={detailsButton} />
          </ErrorBoundary>
        </section>
      </main>

      <ErrorBoundary>
        <HowWeGotThis run={run} strip={strip} open={detailsOpen} onClose={closeDetails}
          showTechnical={showTechnical} onToggleTechnical={setShowTechnical} />
      </ErrorBoundary>
    </div>
  );
}
