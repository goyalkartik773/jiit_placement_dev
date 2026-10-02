import { useMemo, useState } from 'react';
import { Card } from '../../components/ui/Card/Card';
import { badgeColors, BRANCH_COLORS } from '../../components/placements/PlacedStudents/badgePalette';
import type { BranchStatsData } from '../../types/dashboard.types';
import { TimelineChart, type TimelineRow } from './TimelineChart';
import { count, dayShort, monthShort } from './analyticsFormat';

/**
 * Analytics → Timeline tab.
 *
 * COLOURS: the four series use only tokens from `src/styles/_ui.scss`
 * (`--ui-tint-teal-ink`, `--ui-accent`, `--ui-tint-amber-ink`,
 * `--ui-tint-violet-ink`) — see `TimelineChart.tsx`.
 *
 * Cumulative figures are read straight off the payload (`cumoffers`,
 * `cumstudents`, `cumaveragepackage`, `cummedianpackage`) rather than summed
 * here: a cumulative MEDIAN cannot be rebuilt from per-month medians, and a
 * cumulative distinct-student count would double-count anyone who appears in
 * two months (360 against a 345-student cohort).
 */

interface TimelineTabProps {
  data: BranchStatsData;
}

interface BranchOption {
  branch: string;
  /** Branch colour for the chip dot. */
  ink: string;
}

export function TimelineTab({ data }: TimelineTabProps) {
  const [cumulative, setCumulative] = useState(false);
  const [granularity, setGranularity] = useState<'month' | 'day'>('month');
  const [show, setShow] = useState<'all' | 'counts' | 'packages'>('all');
  const [branch, setBranch] = useState<string>('__all__');

  const options: BranchOption[] = useMemo(
    () =>
      data.branches.map((entry) => ({
        branch: entry.branch,
        ink: badgeColors(BRANCH_COLORS, entry.branch).text,
      })),
    [data.branches],
  );

  // The endpoint ships a per-branch series by MONTH only — there is no daily
  // breakdown per branch. Rather than let Day + branch silently draw monthly
  // buckets, the branch filter is disabled for the Day view and pinned to "All".
  const branchPinned = granularity === 'day';

  const rows: TimelineRow[] = useMemo(() => {
    // Both bucket kinds are folded into one shape first: `BranchTimelineDayPoint`
    // keys on `day`, the month kinds on `month`, so reading `.month` off the
    // union would be a type error (and a lie on the daily view).
    type Bucket = {
      key: string;
      point: {
        students: number;
        offers: number;
        averagepackage?: number | null;
        medianpackage?: number | null;
        cumstudents?: number;
        cumoffers?: number;
        cumaveragepackage?: number | null;
        cummedianpackage?: number | null;
      };
    };
    const buckets: Bucket[] = branchPinned
      ? (data.daily ?? []).map((point) => ({ key: point.day, point }))
      : branch === '__all__'
        ? data.timeline.map((point) => ({ key: point.month, point }))
        : data.branchtimeline
            .filter((point) => point.branch === branch)
            .map((point) => ({ key: point.month, point }));

    return buckets.map(({ key, point }) => ({
      label: branchPinned ? dayShort(key) : monthShort(key),
      uniqueStudents: cumulative ? (point.cumstudents ?? point.students) : point.students,
      totalOffers: cumulative ? (point.cumoffers ?? point.offers) : point.offers,
      averagePackage: cumulative ? (point.cumaveragepackage ?? point.averagepackage ?? null) : (point.averagepackage ?? null),
      medianPackage: cumulative ? (point.cummedianpackage ?? point.medianpackage ?? null) : (point.medianpackage ?? null),
    }));
  }, [branch, branchPinned, cumulative, data.daily, data.branchtimeline, data.timeline]);

  const scopeLabel = branchPinned || branch === '__all__' ? 'all branches' : branch;
  const modeLabel = cumulative ? 'cumulative' : 'per-period';
  const ariaLabel = `Placement timeline, ${granularity === 'month' ? 'monthly' : 'daily'}, ${modeLabel}, ${scopeLabel}, batch ${data.batch}: ${
    rows.length
  } periods, ending at ${count(rows[rows.length - 1]?.totalOffers ?? 0)} offers and ${count(
    rows[rows.length - 1]?.uniqueStudents ?? 0,
  )} unique students.`;

  return (
    <div className="analytics-tab">
      <div className="analytics-controls" role="group" aria-label="Timeline chart controls">
        <div className="analytics-controls__group">
          <span className="analytics-controls__label" id="tl-view-label">
            View
          </span>
          <div className="analytics-controls__seg" role="group" aria-labelledby="tl-view-label">
            <button
              type="button"
              className={`analytics-seg${!cumulative ? ' is-active' : ''}`}
              aria-pressed={!cumulative}
              onClick={() => setCumulative(false)}
            >
              Individual
            </button>
            <button
              type="button"
              className={`analytics-seg${cumulative ? ' is-active' : ''}`}
              aria-pressed={cumulative}
              onClick={() => setCumulative(true)}
            >
              Cumulative
            </button>
          </div>
        </div>

        <div className="analytics-controls__group">
          <span className="analytics-controls__label" id="tl-grain-label">
            Granularity
          </span>
          <div className="analytics-controls__seg" role="group" aria-labelledby="tl-grain-label">
            <button
              type="button"
              className={`analytics-seg${granularity === 'month' ? ' is-active' : ''}`}
              aria-pressed={granularity === 'month'}
              onClick={() => setGranularity('month')}
            >
              Month
            </button>
            <button
              type="button"
              className={`analytics-seg${granularity === 'day' ? ' is-active' : ''}`}
              aria-pressed={granularity === 'day'}
              onClick={() => setGranularity('day')}
            >
              Day
            </button>
          </div>
        </div>

        <div className="analytics-controls__group">
          <span className="analytics-controls__label" id="tl-series-label">
            Series
          </span>
          <div className="analytics-controls__seg" role="group" aria-labelledby="tl-series-label">
            {(['all', 'counts', 'packages'] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={`analytics-seg${show === value ? ' is-active' : ''}`}
                aria-pressed={show === value}
                onClick={() => setShow(value)}
              >
                {value === 'all' ? 'All' : value === 'counts' ? 'Counts' : 'Packages'}
              </button>
            ))}
          </div>
        </div>

        <div className="analytics-controls__group">
          <label className="analytics-controls__label" htmlFor="tl-branch">
            Branch
          </label>
          <select
            id="tl-branch"
            className="analytics-select"
            value={branchPinned ? '__all__' : branch}
            disabled={branchPinned}
            title={
              branchPinned
                ? 'The endpoint ships per-branch figures by month only — switch Granularity to Month to filter by branch.'
                : undefined
            }
            onChange={(event) => setBranch(event.target.value)}
          >
            <option value="__all__">All branches</option>
            {options.map((option) => (
              <option key={option.branch} value={option.branch}>
                {option.branch}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card as="section" className="analytics-chart" ariaLabel="Placement timeline">
        <header className="analytics-chart__head">
          <div>
            <h2 className="analytics-chart__title">
              {cumulative ? 'Cumulative placement timeline' : 'Placement timeline'}
            </h2>
            <p className="analytics-chart__sub">
              {granularity === 'month' ? 'By month' : 'By day'} · {scopeLabel} · {count(rows.length)} periods. Left axis
              counts, right axis packages in LPA.
            </p>
          </div>
        </header>

        <TimelineChart rows={rows} show={show} ariaLabel={ariaLabel} />

        <ul className="analytics-legend">
          {(show === 'counts' || show === 'all') && (
            <>
              <li className="analytics-legend__item">
                <span
                  className="analytics-legend__swatch analytics-legend__swatch--bar"
                  aria-hidden="true"
                  style={{ background: 'var(--ui-tint-teal-ink)' }}
                />
                Unique students
              </li>
              <li className="analytics-legend__item">
                <span
                  className="analytics-legend__swatch analytics-legend__swatch--bar"
                  aria-hidden="true"
                  style={{ background: 'var(--ui-accent)' }}
                />
                Total offers
              </li>
            </>
          )}
          {(show === 'packages' || show === 'all') && (
            <>
              <li className="analytics-legend__item">
                <span
                  className="analytics-legend__swatch"
                  aria-hidden="true"
                  style={{ background: 'var(--ui-tint-amber-ink)' }}
                />
                Average package (LPA)
              </li>
              <li className="analytics-legend__item">
                <span
                  className="analytics-legend__swatch"
                  aria-hidden="true"
                  style={{ background: 'var(--ui-tint-violet-ink)' }}
                />
                Median package (LPA)
              </li>
            </>
          )}
        </ul>
      </Card>

      <p className="analytics-footnote">
        {cumulative
          ? 'Cumulative figures are computed in SQL over the whole period to date — a cumulative median is a pooled median, not an average of the monthly medians, and unique students are counted distinctly across months.'
          : 'Unique students per period are counted distinctly within that period; the same student can appear in two different periods.'}
      </p>
    </div>
  );
}
