import type { ReactNode } from 'react';
import './DonutChart.scss';

/** One slice. `value` is a head-count, never a percentage — the chart derives. */
export interface DonutSegment {
  label: string;
  value: number;
  /**
   * CSS colour for the slice and its legend swatch. Omitted segments take the
   * default palette in order, which is the token set from `styles/_ui.scss`.
   */
  color?: string;
}

interface DonutChartProps {
  segments: DonutSegment[];
  /**
   * The whole chart in one sentence — prints as the visually-hidden table's
   * caption, which is how assistive tech meets the chart: the ring itself is
   * `aria-hidden` decoration, and every number it draws is repeated in text.
   */
  ariaLabel: string;
  /** Centre figure, already formatted ("420"). Omit to leave the hole empty. */
  centerValue?: ReactNode;
  /** Centre caption under the figure ("placed"). */
  centerLabel?: string;
  className?: string;
}

/**
 * Default palette — tokens only, all >= 3:1 against the panel they sit on, and
 * spaced far enough apart on the wheel that two adjacent slices are never told
 * apart by hue alone (the legend repeats every label in text regardless).
 */
const PALETTE = [
  'var(--ui-tint-accent-ink)',
  'var(--ui-tint-violet-ink)',
  'var(--ui-tint-teal-ink)',
  'var(--ui-tint-amber-ink)',
  'var(--ui-tint-green-ink)',
  'var(--ui-muted)',
];

/**
 * Whole-number shares that add to exactly 100: floor every share, then hand
 * the leftover points to the slices with the largest fractional part
 * (largest-remainder). Plain `Math.round` is what makes a legend read
 * 33 / 33 / 33 = 99 or 34 / 34 / 34 = 102, which is the defect this exists
 * to rule out. Returns all zeros when the total is 0.
 */
function sharePercents(values: number[], total: number): number[] {
  if (total <= 0 || values.length === 0) return values.map(() => 0);

  const floors = values.map((value) => Math.floor((value / total) * 100));
  let leftover = 100 - floors.reduce((sum, pct) => sum + pct, 0);

  const byRemainder = values
    .map((value, index) => ({ index, remainder: (value / total) * 100 - Math.floor((value / total) * 100) }))
    // Largest remainder first; ties break on the larger slice, then on order,
    // so the result is deterministic for a given feed.
    .sort((a, b) => b.remainder - a.remainder || values[b.index] - values[a.index] || a.index - b.index);

  for (const entry of byRemainder) {
    if (leftover <= 0) break;
    floors[entry.index] += 1;
    leftover -= 1;
  }
  return floors;
}

/**
 * A ring chart for part-of-whole counts, with its legend in real text beside
 * it.
 *
 * WHY A LEGEND AND NOT HOVER. A tooltip is the usual way to read a donut and
 * it is unusable without a pointer: on a phone and on a screen reader the
 * chart collapses to coloured arcs nobody can name. So every slice prints its
 * label and share next to the ring, the arcs are `aria-hidden`, and the same
 * numbers ship as a visually-hidden table — the ring is the illustration, the
 * legend and the table are the data.
 *
 * It prints what it is handed: shares are derived from `value` only, and the
 * largest-remainder rule keeps the printed shares summing to 100.
 */
export function DonutChart({
  segments,
  ariaLabel,
  centerValue,
  centerLabel,
  className = '',
}: DonutChartProps) {
  const values = segments.map((segment) => Math.max(0, segment.value));
  const total = values.reduce((sum, value) => sum + value, 0);
  const percents = sharePercents(values, total);

  // Geometry: one ring, arc lengths as dash arrays. A 2px gap separates
  // neighbours, except where a slice owns the whole ring (a gap there would
  // turn "100%" into "almost all").
  const RADIUS = 48;
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
  const GAP = segments.length > 1 ? 2 : 0;

  let offset = 0;
  const arcs =
    total > 0
      ? values.map((value, index) => {
          const length = (value / total) * CIRCUMFERENCE;
          const drawn = Math.max(length - GAP, 1);
          const arc = {
            key: `${segments[index].label}-${index}`,
            color: segments[index].color ?? PALETTE[index % PALETTE.length],
            dash: `${drawn} ${CIRCUMFERENCE - drawn}`,
            offset: -offset,
          };
          offset += length;
          return arc;
        })
      : [];

  const classes = ['ui-donut', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <div className="ui-donut__figure">
        <svg viewBox="0 0 120 120" className="ui-donut__ring" aria-hidden="true" focusable="false">
          <circle className="ui-donut__track" cx="60" cy="60" r={RADIUS} />
          {/* rotate so slice 1 starts at 12 o'clock, the way a share reads */}
          <g transform="rotate(-90 60 60)">
            {arcs.map((arc) => (
              <circle
                key={arc.key}
                className="ui-donut__arc"
                cx="60"
                cy="60"
                r={RADIUS}
                stroke={arc.color}
                strokeDasharray={arc.dash}
                strokeDashoffset={arc.offset}
              />
            ))}
          </g>
        </svg>

        {centerValue !== undefined || centerLabel ? (
          <span className="ui-donut__center">
            {centerValue !== undefined ? <span className="ui-donut__value">{centerValue}</span> : null}
            {centerLabel ? <span className="ui-donut__label">{centerLabel}</span> : null}
          </span>
        ) : null}
      </div>

      <ul className="ui-donut__legend">
        {segments.map((segment, index) => (
          <li className="ui-donut__legend-item" key={`${segment.label}-${index}`}>
            <span
              className="ui-donut__swatch"
              style={{ background: segment.color ?? PALETTE[index % PALETTE.length] }}
              aria-hidden="true"
            />
            <span className="ui-donut__legend-label">{segment.label}</span>
            <span className="ui-donut__legend-value">
              <span className="ui-donut__legend-count">{values[index].toLocaleString()}</span>
              <span className="ui-donut__legend-pct">{percents[index]}%</span>
            </span>
          </li>
        ))}
      </ul>

      {/* The same numbers as a real table — how a screen reader reads a chart */}
      <table className="sr-only">
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">Students</th>
            <th scope="col">Share</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((segment, index) => (
            <tr key={`row-${segment.label}-${index}`}>
              <th scope="row">{segment.label}</th>
              <td>{values[index]}</td>
              <td>{percents[index]}%</td>
            </tr>
          ))}
          <tr>
            <th scope="row">Total</th>
            <td>{total}</td>
            <td>100%</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
