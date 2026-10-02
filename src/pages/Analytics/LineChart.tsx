import { areaPath, linePath, niceCeil, ticksUpTo, useMeasuredWidth, type Point } from './chartUtils';

/**
 * Analytics → Distribution chart.
 *
 * COLOURS: every stroke/fill below is either a design token from
 * `src/styles/_ui.scss` (the accent used for the all-branches line) or a value
 * from `BRANCH_COLORS` in `components/placements/PlacedStudents/badgePalette.ts`
 * (passed in by the caller as `series[].stroke` / `series[].fill`), so a branch
 * line is the same colour as that branch's badge everywhere else in the app.
 * No colour literal is invented here.
 */

export interface ChartSeries {
  /** Stable React key + legend key. */
  key: string;
  /** Legend text. */
  label: string;
  /** Stroke colour — a token or a `BRANCH_COLORS` text colour. */
  stroke: string;
  /** Optional area fill — a `BRANCH_COLORS` background colour. */
  fill?: string;
  /** Dash pattern so two similarly-coloured lines stay tellable apart. */
  dash?: string;
  strokeWidth?: number;
  /** One value per category; `null`/`undefined` breaks the line (no dip). */
  values: (number | null)[];
}

interface LineChartProps {
  /** X-axis labels, left → right (the 15 fine bands). */
  categories: string[];
  series: ChartSeries[];
  /** `area` fills under each line; `line` draws the stroke only. */
  mode: 'area' | 'line';
  /** Unit shown on the Y axis ("offers"). */
  yUnit: string;
  /** `role="img"` label — the whole chart in one sentence. */
  ariaLabel: string;
}

const PAD = { top: 22, right: 20, bottom: 76, left: 58 };
const HEIGHT = 360;
const MIN_WIDTH = 640;

/** Combined-mode dash for the all-branches line (the reference series). */
export const OVERALL_DASH = '7 4';

export function LineChart({ categories, series, mode, yUnit, ariaLabel }: LineChartProps) {
  const [ref, width] = useMeasuredWidth(MIN_WIDTH);

  const innerW = width - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const baseline = PAD.top + innerH;

  const max = niceCeil(
    Math.max(0, ...series.flatMap((entry) => entry.values.map((value) => value ?? 0))),
    4,
  );
  const ticks = ticksUpTo(max, 4);

  const xAt = (index: number) => PAD.left + ((index + 0.5) * innerW) / Math.max(1, categories.length);
  const yAt = (value: number) => baseline - (max > 0 ? value / max : 0) * innerH;

  const pointsFor = (entry: ChartSeries): (Point | null)[] =>
    entry.values.map((value, index) =>
      value === null || value === undefined || !Number.isFinite(value) ? null : { x: xAt(index), y: yAt(value) },
    );

  return (
    <div className="analytics-chart__scroll" ref={ref} tabIndex={0} role="region" aria-label={`${ariaLabel} (scrollable chart)`}>
      <svg
        className="analytics-chart__svg"
        width={width}
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        role="img"
        aria-label={ariaLabel}
      >
        {/* Grid + Y axis (left) */}
        {ticks.map((tick) => {
          const y = yAt(tick);
          return (
            <g key={tick}>
              <line className="analytics-chart__grid" x1={PAD.left} y1={y} x2={width - PAD.right} y2={y} />
              <text className="analytics-chart__axis analytics-chart__axis--y" x={PAD.left - 10} y={y + 4} textAnchor="end">
                {tick.toLocaleString()}
              </text>
            </g>
          );
        })}
        <text className="analytics-chart__axis-unit" x={PAD.left - 10} y={PAD.top - 8} textAnchor="end">
          {yUnit}
        </text>

        {/* Baseline */}
        <line className="analytics-chart__baseline" x1={PAD.left} y1={baseline} x2={width - PAD.right} y2={baseline} />

        {/* Series: areas first so strokes and hover targets sit above them */}
        {mode === 'area'
          ? series
              .filter((entry) => entry.fill)
              .map((entry) => {
                const solid = pointsFor(entry).filter((point): point is Point => point !== null);
                const d = areaPath(solid, baseline);
                return d ? (
                  <path key={`fill-${entry.key}`} d={d} fill={entry.fill as string} fillOpacity={0.45} stroke="none" />
                ) : null;
              })
          : null}

        {series.map((entry) => {
          const d = linePath(pointsFor(entry));
          if (!d) return null;
          return (
            <path
              key={entry.key}
              d={d}
              fill="none"
              stroke={entry.stroke}
              strokeWidth={entry.strokeWidth ?? 2}
              strokeDasharray={entry.dash}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          );
        })}

        {/* Hover targets — one invisible column per category with a native tooltip */}
        {categories.map((category, index) => {
          const slot = innerW / Math.max(1, categories.length);
          const summary = series
            .map((entry) => `${entry.label} ${entry.values[index] ?? '—'}`)
            .join(' · ');
          return (
            <rect
              key={`hover-${category}`}
              className="analytics-chart__hit"
              x={xAt(index) - slot / 2}
              y={PAD.top}
              width={slot}
              height={innerH}
              pointerEvents="all"
            >
              <title>{`${category}: ${summary}`}</title>
            </rect>
          );
        })}

        {/* X-axis labels, rotated so long names like "Not disclosed" fit */}
        {categories.map((category, index) => {
          const x = xAt(index);
          const y = baseline + 18;
          return (
            <text
              key={`x-${category}`}
              className="analytics-chart__axis analytics-chart__axis--x"
              x={x}
              y={y}
              transform={`rotate(-40 ${x} ${y})`}
              textAnchor="end"
            >
              {category}
            </text>
          );
        })}
      </svg>

      {/* The same numbers as a real table — how a screen reader actually reads a chart */}
      <table className="sr-only">
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Band</th>
            {series.map((entry) => (
              <th scope="col" key={entry.key}>
                {entry.label} ({yUnit})
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {categories.map((category, index) => (
            <tr key={`row-${category}`}>
              <th scope="row">{category}</th>
              {series.map((entry) => (
                <td key={entry.key}>{entry.values[index] ?? 'no data'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
