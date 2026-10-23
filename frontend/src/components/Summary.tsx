import type { RefObject } from "react";
import type { RunState } from "../state/runState";
import type { SummaryModel } from "../view/summaryModel";
import { buttonSecondary } from "./buttonStyles";
import { ReviewNotice } from "./ReviewNotice";

interface Props {
  run: RunState;
  summary: SummaryModel;
  detailsOpen: boolean;
  onToggleDetails: () => void;
  detailsButtonRef: RefObject<HTMLButtonElement | null>;
}

export function Summary({ run, summary, detailsOpen, onToggleDetails, detailsButtonRef }: Props) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="summary-title" className="font-serif text-xl font-semibold">
          Your summary
        </h2>
        <button
          ref={detailsButtonRef}
          type="button"
          className={buttonSecondary}
          aria-expanded={detailsOpen}
          aria-controls="details-panel"
          onClick={onToggleDetails}
          disabled={run.events.length === 0}
        >
          How we got this
        </button>
      </div>

      <div className="mt-4 max-w-[62ch] space-y-6 font-serif text-lg leading-relaxed">
        {summary.stage === "idle" && <p className="text-ink-soft">Choose a case, then select Run case.</p>}

        {summary.stage === "working" && (
          <p className="text-ink-soft">Your care team is working on this. Your summary will appear here.</p>
        )}

        {summary.stage === "review" && <ReviewNotice review={run.review} flags={run.redFlags} />}

        {summary.stage === "empty" && (
          <p>No summary was produced for this case. Ask a healthcare professional to look at the results directly.</p>
        )}

        {/* Missing parts come before the sections: a reader should know what is not covered. */}
        {summary.gaps.length > 0 && (
          <div role="note" className="border-l-2 border-ink pl-4 font-sans">
            <h3 className="font-bold">Part of this review is missing</h3>
            <ul className="mt-1 list-disc pl-5">
              {summary.gaps.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          </div>
        )}

        {summary.sections.map((section) => (
          <article key={section.id} className="section-in border-l-2 border-line pl-4">
            <h3 className="text-xl font-semibold">{section.title}</h3>
            <p className="mt-1">{section.text}</p>
            {section.basedOn.length > 0 && (
              <p className="mt-2 font-sans text-sm text-ink-soft">Based on: {section.basedOn.join(", ")}</p>
            )}
          </article>
        ))}

        {summary.limitations.length > 0 && (
          <div className="font-sans text-ink-soft">
            <h3 className="font-bold text-ink">What this summary can&apos;t tell you</h3>
            <ul className="mt-1 list-disc pl-5">
              {summary.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
