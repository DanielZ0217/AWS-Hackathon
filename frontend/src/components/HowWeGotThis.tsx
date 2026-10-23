import { useEffect, useRef } from "react";
import { decisionLabel, shortModelName, statusLabel, stepLabel, workerLabel } from "../labels";
import type { RunState } from "../state/runState";
import { modelCallTotals, visibleEvents } from "../state/runState";
import type { StripModel } from "../view/stripModel";
import { buttonSecondary } from "./buttonStyles";

interface Props {
  run: RunState;
  strip: StripModel;
  open: boolean;
  onClose: () => void;
  showTechnical: boolean;
  onToggleTechnical: (next: boolean) => void;
}

const unknown = (value: number | null, format: (n: number) => string = String) =>
  value === null ? "Not reported" : format(value);

export function HowWeGotThis({ run, strip, open, onClose, showTechnical, onToggleTechnical }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Move focus into the panel once, when it opens (not on every update while it is open).
  useEffect(() => {
    if (open) headingRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const totals = modelCallTotals(run);

  return (
    <aside
      id="details-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="details-title"
      className="fixed inset-y-0 right-0 z-10 w-full max-w-md overflow-y-auto border-l border-ink bg-surface p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <h2 id="details-title" ref={headingRef} tabIndex={-1} className="text-xl font-bold">
          How we got this
        </h2>
        <button type="button" className={buttonSecondary} onClick={onClose}>
          Close
        </button>
      </div>

      <div className="mt-5 space-y-6">
        <section>
          <h3 className="font-bold">Who looked at what</h3>
          {run.workers.length === 0 ? (
            <p className="mt-1 text-ink-soft">No one has started yet.</p>
          ) : (
            <ul className="mt-2 space-y-3">
              {run.workers.map((card) => (
                <li key={card.worker} className="border-l-2 border-line pl-3">
                  <p>
                    <span className="font-bold">{workerLabel(card.worker)}</span>: {statusLabel(card.status)}
                  </p>
                  {card.question && <p className="text-ink-soft">Question: {card.question}</p>}
                  {card.summary && <p>{card.summary}</p>}
                  {card.limitations.map((limit) => (
                    <p key={limit} className="text-ink-soft">
                      Limit: {limit}
                    </p>
                  ))}
                  {card.error && (
                    <p>
                      {card.error.limitation ?? "This part could not be reviewed."} {card.error.nextAction}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="font-bold">What was passed to the doctor</h3>
          {strip.handoffs.length === 0 ? (
            <p className="mt-1 text-ink-soft">Nothing has been passed on yet.</p>
          ) : (
            <ul className="mt-2 list-disc pl-5">
              {strip.handoffs.map((h) => (
                <li key={h.fromRow}>
                  {workerLabel(h.fromRow)}: {h.kind === "result" ? "sent a result" : "no result, it couldn't be reviewed"}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="font-bold">The doctor&apos;s decision</h3>
          {run.doctor ? (
            <>
              <p className="mt-1">{decisionLabel(run.doctor.decision)}</p>
              {run.doctor.reason && <p className="text-ink-soft">{run.doctor.reason}</p>}
            </>
          ) : (
            <p className="mt-1 text-ink-soft">Not reached yet.</p>
          )}
        </section>

        <section>
          <h3 className="font-bold">Red flags</h3>
          {run.redFlags.length === 0 ? (
            <p className="mt-1 text-ink-soft">None raised.</p>
          ) : (
            <ul className="mt-2 list-disc pl-5">
              {run.redFlags.map((flag) => (
                <li key={flag.id}>
                  {flag.description}
                  {flag.requiresHumanReview && " A healthcare professional must review this."}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="font-bold">Every step, in order</h3>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            {visibleEvents(run, "audit").map((event) => (
              <li key={event.event_id}>{event.summary}</li>
            ))}
          </ol>
        </section>

        <section className="border-t border-line pt-4">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={showTechnical}
              onChange={(e) => onToggleTechnical(e.target.checked)}
              className="mt-1 h-5 w-5 accent-ink"
            />
            <span>
              <span className="font-bold">Show technical details</span>
              <span className="block text-sm text-ink-soft">
                For care teams and reviewers: the model calls behind each step.
              </span>
            </span>
          </label>

          {showTechnical && (
            <div className="mt-4 space-y-4">
              {run.modelCalls.length === 0 ? (
                <p className="text-ink-soft">No model calls recorded yet.</p>
              ) : (
                <table className="w-full text-left text-sm">
                  <caption className="mb-1 text-left font-bold">Model calls</caption>
                  <thead>
                    <tr className="border-b border-line">
                      <th className="py-1 pr-2">Step</th>
                      <th className="py-1 pr-2">Model</th>
                      <th className="py-1 pr-2">In</th>
                      <th className="py-1 pr-2">Out</th>
                      <th className="py-1">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.modelCalls.map((call) => (
                      <tr key={call.eventId} className="border-b border-line align-top">
                        <td className="py-1 pr-2">{stepLabel(call.actor)}</td>
                        <td className="py-1 pr-2">{shortModelName(call.model)}</td>
                        <td className="py-1 pr-2">{unknown(call.inputTokens)}</td>
                        <td className="py-1 pr-2">{unknown(call.outputTokens)}</td>
                        <td className="py-1">{unknown(call.durationMs, (ms) => `${(ms / 1000).toFixed(1)} s`)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="font-bold">
                      <td className="py-1 pr-2">Total ({totals.calls})</td>
                      <td />
                      <td className="py-1 pr-2">{totals.inputTokens}</td>
                      <td className="py-1 pr-2">{totals.outputTokens}</td>
                      <td className="py-1">{(totals.durationMs / 1000).toFixed(1)} s</td>
                    </tr>
                  </tfoot>
                </table>
              )}

              {run.recovery.queries.length > 0 && (
                <div>
                  <h4 className="font-bold">Extra source searches</h4>
                  <ul className="mt-1 list-disc pl-5 text-sm">
                    {run.recovery.queries.map((q) => (
                      <li key={`${q.kind}-${q.text}`}>
                        {q.kind}: {q.text}
                        {q.isSearchAid && <em> (a search aid, not evidence)</em>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}
