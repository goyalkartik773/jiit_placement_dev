import { labelStride, linePath, niceCeil, ticksUpTo, useMeasuredWidth, type Point } from './chartUtils';

/**
 * Analytics → Timeline chart (dual axis).
 *
 * COLOURS: all four series colours are design tokens from
 * `src/styles/_ui.scss` (`--ui-tint-teal-ink`, `--ui-accent`,
 * `--ui-tint-amber-ink`, `--ui-tint-violet-ink`) — no colour literal is
 * invented here. Counts share the LEFT axis; packages share the RIGHT axis, so
 * a ₹56 L package never has to share a scale with a 172-offer month.
 */

export interface TimelineRow {
  /** Display bucket label ("Apr 26" / "15 Apr"). */
  label: string;
  uniqueStudents: number;
  totalOffers: number;
  /** LPA; null renders as a break in the line, never a 0. */
  averagePackage: number | null;
  medianPackage: number | null;
}

interface TimelineChartProps {
  rows: TimelineRow[];
  /** Which of the three series groups are on screen. */
  show: 'all' | 'counts' | 'packages';
  /** `role="img"` label — the whole chart in one sentence. */
  ariaLabel: string;
}

const PAD = { top: 26, right: 58, bottom: 54, left: 58 };
const HEIGHT = 380;
const MIN_WIDTH = 660;

export function TimelineChart({ rows, show, ariaLabel }: TimelineChartProps) {
  const [ref, width] = useMeasuredWidth(MIN_WIDTH);

  const showCounts = show === 'all' || show === 'counts';
  const showPackages = show === 'all' || show === 'packages';

  const innerW = width - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const baseline = PAD.top + innerH;

  const countMax = niceCeil(Math.max(0, ...rows.map((row) => Math.max(row.uniqueStudents, row.totalOffers))), 4);
  const packageMax = niceCeil(
    Math.max(0, ...rows.flatMap((row) => [row.averagePackage ?? 0, row.medianPackage ?? 0])),
    4,
  );
  const countTicks = ticksUpTo(countMax, 4);
  const packageTicks = ticksUpTo(packageMax, 4);

  const slot = innerW / Math.max(1, rows.length);
  const xAt = (index: number) => PAD.left + (index + 0.5) * slot;
  const yCount = (value: number) => baseline - (countMax > 0 ? value / countMax : 0) * innerH;
  const yPackage = (value: number) => baseline - (packageMax > 0 ? value / packageMax : 0) * innerH;

  // Two grouped bars per bucket; clamped so a 54-day view stays legible.
  const barW = Math.max(2, Math.min(slot * 0.32, 20));
  const groupW = barW * 2 + 3;

  const lineFor = (pick: (row: TimelineRow) => number | null): string => {
    const points: (Point | null)[] = rows.map((row, index) => {
      const value = pick(row);
      return value === null || value === undefined || !Number.isFinite(value) ? null : { x: xAt(index), y: yPackage(value) };
    });
    return linePath(points);
  };

  const xStride = labelStride(rows.length, Math.max(4, Math.floor(innerW / 64)));

  return (
    <div
      className="analytics-chart__scroll"
      ref={ref}
      tabIndex={0}
      role="region"
      aria-label={`${ariaLabel} (scrollable chart)`}
    >
      <svg
        className="analytics-chart__svg"
        width={width}
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        role="img"
        aria-label={ariaLabel}
      >
        {/* Left axis — counts */}
        {showCounts
          ? countTicks.map((tick) => {
              const y = yCount(tick);
              return (
                <g key={`c-${tick}`}>
                  <line className="analytics-chart__grid" x1={PAD.left} y1={y} x2={width - PAD.right} y2={y} />
                  <text className="analytics-chart__axis analytics-chart__axis--y" x={PAD.left - 10} y={y + 4} textAnchor="end">
                    {tick.toLocaleString()}
                  </text>
                </g>
              );
            })
          : null}
        {showCounts ? (
          <text className="analytics-chart__axis-unit" x={PAD.left - 10} y={PAD.top - 10} textAnchor="end">
            students / offers
          </text>
        ) : null}

        {/* Right axis — LPA */}
        {showPackages
          ? packageTicks.map((tick) => {
              const y = yPackage(tick);
              return (
                <text
                  key={`p-${tick}`}
                  className="analytics-chart__axis analytics-chart__axis--y"
                  x={width - PAD.right + 10}
                  y={y + 4}
                  textAnchor="start"
                >
                  {tick.toLocaleString()}
                </text>
              );
            })
          : null}
        {showPackages ? (
          <text className="analytics-chart__axis-unit" x={width - PAD.right + 10} y={PAD.top - 10} textAnchor="start">
            LPA
          </text>
        ) : null}

        {/* Bars — unique students then total offers, side by side */}
        {showCounts
          ? rows.map((row, index) => {
              const centre = xAt(index);
              const studentsH = baseline - yCount(row.uniqueStudents);
              const offersH = baseline - yCount(row.totalOffers);
              const left = centre - groupW / 2;
              return (
                <g key={`bars-${row.label}`}>
                  <rect
                    className="analytics-chart__bar analytics-chart__bar--students"
                    x={left}
                    y={baseline - studentsH}
                    width={barW}
                    height={studentsH}
                  >
                    <title>{`${row.label} — unique students: ${row.uniqueStudents.toLocaleString()}`}</title>
                  </rect>
                  <rect
                    className="analytics-chart__bar analytics-chart__bar--offers"
                    x={left + barW + 3}
                    y={baseline - offersH}
                    width={barW}
                    height={offersH}
                  >
                    <title>{`${row.label} — total offers: ${row.totalOffers.toLocaleString()}`}</title>
                  </rect>
                </g>
              );
            })
          : null}

        {/* Lines — average then median (median dashed so the pair stays readable) */}
        {showPackages ? (
          <>
            {(() => {
              const d = lineFor((row) => row.averagePackage);
              return d ? <path className="analytics-chart__line analytics-chart__line--avg" d={d} /> : null;
            })()}
            {(() => {
              const d = lineFor((row) => row.medianPackage);
              return d ? <path className="analytics-chart__line analytics-chart__line--median" d={d} /> : null;
            })()}
          </>
        ) : null}

        {/* Hover targets with a native tooltip carrying the full row */}
        {rows.map((row, index) => (
          <rect
            key={`hover-${row.label}`}
            className="analytics-chart__hit"
            x={xAt(index) - slot / 2}
            y={PAD.top}
            width={slot}
            height={innerH}
            pointerEvents="all"
          >
            <title>
              {`${row.label} — students ${row.uniqueStudents.toLocaleString()}, offers ${row.totalOffers.toLocaleString()}, avg ${
                row.averagePackage === null ? '—' : row.averagePackage
              } LPA, median ${row.medianPackage === null ? '—' : row.medianPackage} LPA`}
            </title>
          </rect>
        ))}

        <line className="analytics-chart__baseline" x1={PAD.left} y1={baseline} x2={width - PAD.right} y2={baseline} />

        {/* X labels, strided so 54 daily buckets do not collide */}
        {rows.map((row, index) =>
          index % xStride === 0 ? (
            <text
              key={`x-${row.label}`}
              className="analytics-chart__axis analytics-chart__axis--x"
              x={xAt(index)}
              y={baseline + 20}
              textAnchor="middle"
            >
              {row.label}
            </text>
          ) : null,
        )}
      </svg>

      {/* The same numbers as a real table — how a screen reader reads a chart */}
      <table className="sr-only">
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Period</th>
            <th scope="col">Unique students</th>
            <th scope="col">Total offers</th>
            <th scope="col">Average package (LPA)</th>
            <th scope="col">Median package (LPA)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`row-${row.label}`}>
              <th scope="row">{row.label}</th>
              <td>{row.uniqueStudents.toLocaleString()}</td>
              <td>{row.totalOffers.toLocaleString()}</td>
              <td>{row.averagePackage === null ? 'no data' : row.averagePackage}</td>
              <td>{row.medianPackage === null ? 'no data' : row.medianPackage}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
