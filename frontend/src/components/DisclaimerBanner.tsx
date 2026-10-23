export function DisclaimerBanner({ replay }: { replay: boolean }) {
  return (
    <div role="note" className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-sm">
        <p className="font-bold">Prototype using synthetic data. Not medical advice.</p>
        {replay && (
          <p className="flex items-center gap-2 text-ink-soft">
            <span className="rounded-full border border-ink-soft px-2 text-xs font-bold">Replay</span>
            A scripted case, not a live run.
          </p>
        )}
      </div>
    </div>
  );
}
