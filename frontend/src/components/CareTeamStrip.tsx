import { useEffect, useRef } from "react";
import type { ReactElement } from "react";
import { DOCTOR_ROW, statusLabel, workerColor, workerLabel } from "../labels";
import type { StripMark, StripModel } from "../view/stripModel";

// Draws the care team strip from a StripModel. All layout decisions live in stripModel.ts;
// this file only turns numbers into shapes.
//
// Two parts side by side: the row labels (HTML, pinned to the left edge while the strip
// scrolls) and the plot (SVG, which scrolls horizontally on narrow screens and follows the
// newest event).

const ROW_H = 56;
const LABEL_W = 176;
const COL_W = 72;
const MIN_COLS = 12; // an empty strip still shows chart paper
const MIN_ROWS = 3;
const PAD_TOP = 28; // room for the "Review needed" note
const PAD_BOTTOM = 8;
const PAD_RIGHT = 16;
const FADED = 0.45;
const NOTE_ROOM = 110; // width of the "Review needed" note beside the red line
const HANDOFF_STAGGER_MS = 350; // gap between one handoff line drawing in and the next

function MarkShape({ mark, cx, cy }: { mark: StripMark; cx: number; cy: number }): ReactElement {
  const color = workerColor(mark.row);
  const diamond = (r: number) => `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`;
  let shape: ReactElement;

  switch (mark.kind) {
    case "started":
      shape = <circle cx={cx} cy={cy} r={7} strokeWidth={2.5} style={{ fill: "var(--color-paper)", stroke: color }} />;
      break;
    case "completed":
      shape = <circle cx={cx} cy={cy} r={7} style={{ fill: color }} />;
      break;
    case "partial":
      shape = (
        <>
          <circle cx={cx} cy={cy} r={7} style={{ fill: color }} />
          <circle cx={cx} cy={cy} r={11} fill="none" strokeWidth={1.5} strokeDasharray="3 3" style={{ stroke: color }} />
        </>
      );
      break;
    case "failed":
    case "timed_out":
      shape = (
        <>
          <circle cx={cx} cy={cy} r={9} style={{ fill: "var(--color-paper)" }} />
          <g strokeWidth={3} strokeLinecap="round" style={{ stroke: "var(--color-ink-soft)" }}>
            <line x1={cx - 5} y1={cy - 5} x2={cx + 5} y2={cy + 5} />
            <line x1={cx - 5} y1={cy + 5} x2={cx + 5} y2={cy - 5} />
          </g>
        </>
      );
      break;
    case "searching":
      shape = <polygon points={diamond(6)} strokeWidth={2} style={{ fill: "var(--color-paper)", stroke: color }} />;
      break;
    case "gap":
      shape = <polygon points={diamond(6)} style={{ fill: "var(--color-ink-soft)" }} />;
      break;
    case "recovery":
      shape = (
        <>
          <polygon points={diamond(8)} strokeWidth={2} style={{ fill: "var(--color-paper)", stroke: color }} />
          <circle cx={cx} cy={cy} r={2} style={{ fill: color }} />
        </>
      );
      break;
    case "verified":
      shape = <polygon points={diamond(6)} style={{ fill: color }} />;
      break;
    case "reviewed":
      shape = <rect x={cx - 7} y={cy - 7} width={14} height={14} rx={2} style={{ fill: color }} />;
      break;
    case "checked":
      shape = (
        <rect x={cx - 7} y={cy - 7} width={14} height={14} rx={2} strokeWidth={2.5} style={{ fill: "var(--color-paper)", stroke: color }} />
      );
      break;
    case "review_required":
      shape = (
        <>
          <polygon points={`${cx},${cy - 10} ${cx + 10},${cy + 8} ${cx - 10},${cy + 8}`} style={{ fill: "var(--color-alarm)" }} />
          <text x={cx} y={cy + 5} textAnchor="middle" fontSize={12} fontWeight={700} style={{ fill: "var(--color-surface)" }}>
            !
          </text>
        </>
      );
      break;
  }

  return (
    <g>
      <title>{`${workerLabel(mark.row)}: ${mark.label}`}</title>
      {shape}
      {mark.flagged && mark.kind !== "review_required" && (
        <circle cx={cx} cy={cy} r={12} fill="none" strokeWidth={2} style={{ stroke: "var(--color-alarm)" }} />
      )}
    </g>
  );
}

export function CareTeamStrip({ model }: { model: StripModel }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const cols = Math.max(model.columnCount, MIN_COLS);
  const rowSlots = Math.max(model.rows.length, MIN_ROWS);
  const plotWidth = cols * COL_W + PAD_RIGHT;
  const plotBottom = PAD_TOP + rowSlots * ROW_H;
  const height = plotBottom + PAD_BOTTOM;

  const cx = (col: number) => col * COL_W + COL_W / 2;
  const rowIndex = new Map(model.rows.map((row, i) => [row.id, i]));
  const cy = (rowId: string) => PAD_TOP + (rowIndex.get(rowId) ?? 0) * ROW_H + ROW_H / 2;
  // While frozen for review, everything fades except what carries the red flag.
  const fade = (flagged: boolean) => (model.frozen && !flagged ? FADED : 1);

  // On a narrow screen the plot is wider than the viewport. Keep the newest event (or the red
  // flag, once frozen) in view. Does nothing when everything already fits.
  const frozen = model.frozen;
  const followColumn = frozen && model.alarmColumn !== null ? model.alarmColumn : model.columnCount - 1;
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const visiblePlot = el.clientWidth - LABEL_W;
    // While frozen, leave room to the right of the red line for its "Review needed" note.
    const noteRoom = frozen ? NOTE_ROOM : 0;
    const left = followColumn < 0 ? 0 : Math.max(0, (followColumn + 1) * COL_W + PAD_RIGHT + noteRoom - visiblePlot);
    el.scrollTo({ left });
  }, [followColumn, frozen]);

  const description =
    model.rows.length === 0
      ? "Care team progress: no case is running."
      : `Care team progress. ${model.rows.map((r) => `${workerLabel(r.id)}: ${statusLabel(r.status).toLowerCase()}.`).join(" ")}${
          model.frozen ? " Review needed." : ""
        }`;

  const alarmX = model.alarmColumn !== null ? cx(model.alarmColumn) : 0;
  const flipAlarmNote = alarmX + 110 > plotWidth; // keep the note inside the plot near the right edge

  return (
    <div ref={scrollRef} className="overflow-x-auto border border-line bg-surface">
      <div className="flex" style={{ width: "max-content", minWidth: "100%" }}>
        {/* Row labels. Pinned to the left edge while the plot scrolls. The SVG below carries the
            text description for screen readers, so these are hidden from them. */}
        <div
          aria-hidden="true"
          className="sticky left-0 z-10 shrink-0 border-r border-grid-major bg-surface"
          style={{ width: LABEL_W, paddingTop: PAD_TOP, paddingBottom: PAD_BOTTOM }}
        >
          {Array.from({ length: rowSlots }, (_, i) => {
            const row = model.rows[i];
            return (
              <div
                key={row?.id ?? `empty-${i}`}
                className={`flex flex-col justify-center border-t border-grid-major px-3 ${i === rowSlots - 1 ? "border-b" : ""}`}
                style={{ height: ROW_H }}
              >
                {row && (
                  <>
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: workerColor(row.id) }} />
                      <span className="text-[15px] font-bold leading-tight">{workerLabel(row.id)}</span>
                    </div>
                    <span className="pl-[18px] text-sm text-ink-soft">{statusLabel(row.status)}</span>
                  </>
                )}
              </div>
            );
          })}
        </div>

        <svg role="img" aria-label={description} width={plotWidth} height={height} viewBox={`0 0 ${plotWidth} ${height}`}>
          {/* Chart-paper grid: one column per event step, a heavier line every fifth. */}
          {Array.from({ length: cols + 1 }, (_, i) => (
            <line
              key={`v${i}`}
              x1={i * COL_W}
              x2={i * COL_W}
              y1={PAD_TOP}
              y2={plotBottom}
              strokeWidth={1}
              style={{ stroke: i % 5 === 0 ? "var(--color-grid-major)" : "var(--color-grid)" }}
            />
          ))}
          {Array.from({ length: rowSlots + 1 }, (_, i) => (
            <line
              key={`h${i}`}
              x1={0}
              x2={plotWidth}
              y1={PAD_TOP + i * ROW_H}
              y2={PAD_TOP + i * ROW_H}
              strokeWidth={1}
              style={{ stroke: "var(--color-grid-major)" }}
            />
          ))}

          {model.rows.length === 0 && (
            <>
              {/* A paper-colored patch keeps the sentence readable over the grid lines. */}
              <rect x={8} y={PAD_TOP + ROW_H - 12} width={400} height={32} style={{ fill: "var(--color-surface)" }} />
              <text x={16} y={PAD_TOP + ROW_H + 9} fontSize={15} style={{ fill: "var(--color-ink-soft)" }}>
                Your care team will appear here once a case is running.
              </text>
            </>
          )}

          {/* Bars: a worker's activity from start to finish. They grow as events arrive. */}
          {model.bars.map((bar) => {
            const w = cx(bar.toCol) - cx(bar.fromCol) + 12;
            return (
              <rect
                key={`bar-${bar.row}`}
                className="bar-grow"
                x={cx(bar.fromCol) - 6}
                y={cy(bar.row) - 4}
                width={w}
                height={8}
                rx={4}
                opacity={0.35 * fade(false)}
                style={{ fill: workerColor(bar.row), width: w }}
              />
            );
          })}

          {/* Handoffs: a finished worker passing its result (or its gap) to the doctor. */}
          {[...model.handoffs].sort((a, b) => a.fromCol - b.fromCol).map((h, order) => {
            const x1 = cx(h.fromCol);
            const x2 = cx(h.toCol);
            const y1 = cy(h.fromRow);
            const y2 = cy(DOCTOR_ROW);
            const mid = (x1 + x2) / 2;
            return (
              <path
                key={`handoff-${h.fromRow}`}
                d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                fill="none"
                strokeWidth={2}
                opacity={fade(false)}
                pathLength={h.kind === "result" ? 1 : undefined}
                strokeDasharray={h.kind === "gap" ? "6 4" : undefined}
                className={h.kind === "result" ? "handoff-draw" : "fade-in"}
                style={{
                  stroke: h.kind === "result" ? workerColor(h.fromRow) : "var(--color-ink-soft)",
                  // Lines draw in the order the specialists finished, one after another.
                  animationDelay: `${order * HANDOFF_STAGGER_MS}ms`,
                }}
              />
            );
          })}

          {/* Marks */}
          {model.marks.map((mark) => (
            <g key={mark.eventId} opacity={fade(mark.flagged)}>
              <MarkShape mark={mark} cx={cx(mark.col)} cy={cy(mark.row)} />
            </g>
          ))}

          {/* The one red element: where the red flag appeared. */}
          {model.frozen && model.alarmColumn !== null && (
            <g>
              <line x1={alarmX} x2={alarmX} y1={PAD_TOP - 8} y2={plotBottom} strokeWidth={2} style={{ stroke: "var(--color-alarm)" }} />
              <text
                x={flipAlarmNote ? alarmX - 8 : alarmX + 8}
                y={16}
                textAnchor={flipAlarmNote ? "end" : "start"}
                fontSize={13}
                fontWeight={700}
                style={{ fill: "var(--color-alarm)" }}
              >
                Review needed
              </text>
            </g>
          )}
        </svg>
      </div>
    </div>
  );
}
