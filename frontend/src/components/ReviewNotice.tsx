import type { RedFlag } from "../state/payloadAdapters";
import type { ReviewState } from "../state/runState";

// The one red element in the summary. There is deliberately no resume button: the backend has
// not defined how a human review is confirmed, and this screen must not pretend otherwise.
export function ReviewNotice({ review, flags }: { review: ReviewState; flags: RedFlag[] }) {
  return (
    <section role="alert" className="border-l-4 border-alarm bg-surface p-4 font-sans">
      <h3 className="text-lg font-bold text-alarm">A healthcare professional needs to review this</h3>
      {review.reason && <p className="mt-1">{review.reason}.</p>}
      {flags.length > 0 && (
        <ul className="mt-2 list-disc pl-5">
          {flags.map((flag) => (
            <li key={flag.id}>{flag.description}</li>
          ))}
        </ul>
      )}
      <p className="mt-2 font-bold">No guidance will be shown until that review happens.</p>
    </section>
  );
}
