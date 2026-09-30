import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchBranchStats } from '../../../services/placementService';
import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
import { ListSkeleton } from '../../common/ListSkeleton/ListSkeleton';
import { ErrorState } from '../../common/ErrorState/ErrorState';
import { Card } from '../../ui/Card/Card';
import type { BranchStat, BranchStatsData } from '../../../types/dashboard.types';
import './BranchStats.scss';

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_LONG = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/** '2025-08' -> { short: 'Aug 25', long: 'August 2025' }; null when malformed. */
function parseMonth(month: string): { short: string; long: string } | null {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return null;
  const index = Number(match[2]) - 1;
  if (index < 0 || index > 11) return null;
  return { short: `${MONTH_SHORT[index]} ${match[1].slice(2)}`, long: `${MONTH_LONG[index]} ${match[1]}` };
}

/** Package figures arrive in LPA; null is a real "not disclosed" answer. */
function lpa(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—';
  return value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function count(value: number): string {
  return Number.isFinite(value) ? value.toLocaleString() : '0';
}

/** Percentage as shown to the user - one or two decimals, never a long float. */
function percent(value: number): string {
  if (!Number.isFinite(value)) return '0';
  return value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

/** 0-100 with a 2% floor so a non-zero bar is always visible. */
function barWidth(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.min(100, Math.max(2, value));
}

/** Count for one band inside one row; a missing band means zero students. */
function bandCount(distribution: BranchStat['distribution'], band: string): number {
  return distribution.find((item) => item.band === band)?.students ?? 0;
}

function bandTone(band: string): string {
  if (/not disclosed/i.test(band)) return 'none';
  if (/^upto/i.test(band)) return 'low';
  if (/13/i.test(band)) return 'high';
  return 'mid';
}

function BandSwatch({ band }: { band: string }) {
  return <span className={`branch-stats__swatch branch-stats__swatch--${bandTone(band)}`} aria-hidden="true" />;
}

/**
 * Branch-wise placement statistics for the graduating batch (additive block
 * on the Company-Wise page, no separate route).
 *
 * Every figure comes from `fn_api_select_branch_stats_v1`: the head-count
 * denominators are the reference config's hardcoded student_counts, packages
 * are `offers.ctc_total` taken once per student, and the timeline buckets
 * `emails.received_at` (the offer mail's arrival, not the backfill timestamp).
 *
 * Accessibility: each block is a real table with a `sr-only` caption and
 * `scope`d headers; the only decorative marks are the bars, which are
 * `aria-hidden` and always accompanied by their exact numbers as text.
 */
export function BranchStats() {
  const [data, setData] = useState<BranchStatsData | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [chartBranch, setChartBranch] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    let alive = true;

    setLoading(true);
    setError(null);
    fetchBranchStats(controller.signal)
      .then((result) => {
        if (alive) setData(result);
      })
      .catch((reason: unknown) => {
        if (!alive) return;
        const failure = reason as { name?: string; message?: string };
        if (failure?.name === 'AbortError') return;
        setError(new Error(failure?.message || 'Could not load branch statistics'));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
      controller.abort();
    };
  }, [attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  /** Order of the four JIIT bands, taken from the totals row (always complete). */
  const bandOrder = useMemo(() => {
    const fromTotals = data?.totals.distribution.map((band) => band.band) ?? [];
    if (fromTotals.length > 0) return fromTotals;
    return data?.branches[0]?.distribution.map((band) => band.band) ?? [];
  }, [data]);

  /** Timeline for the chart: all branches, or exactly the selected one. */
  const chartRows = useMemo(() => {
    if (!data) return [];
    if (!chartBranch) return data.timeline;
    return data.branchtimeline.filter((point) => point.branch === chartBranch);
  }, [data, chartBranch]);

  const maxOffers = useMemo(() => Math.max(1, ...chartRows.map((point) => point.offers)), [chartRows]);

  const summary = data?.totals ?? null;

  return (
    <Card as="section" className="branch-stats" ariaLabel="Branch-wise placement statistics">
      <header className="branch-stats__head">
        <div className="branch-stats__head-text">
          <h2 className="branch-stats__title">Branch-wise statistics</h2>
          <p className="branch-stats__sub">
            {summary ? (
              <>
                Batch {data?.batch || '—'} · graduating {data?.graduatingbatch || '—'} ·{' '}
                <strong>
                  {count(summary.placedstudents)} of {count(summary.totalstudents)} placed (
                  {percent(summary.placementpercentage)}%)
                </strong>{' '}
                · {count(summary.totaloffers)} offers from {count(summary.companies)} companies ·{' '}
                {count(summary.studentswithpackage)} packages disclosed
              </>
            ) : (
              'Loading the batch breakdown...'
            )}
          </p>
        </div>
        {error && data ? (
          <Button variant="soft" size="sm" icon="refresh" onClick={retry}>
            Retry
          </Button>
        ) : null}
      </header>

      {loading && !data ? <ListSkeleton count={3} label="Loading branch statistics" /> : null}

      {error && !data ? (
        <ErrorState title="Could not load branch statistics" message={error.message} onRetry={retry} />
      ) : null}

      {data && summary ? (
        <>
          {/* ---------- Per-branch table ---------- */}
          <div
            className="branch-stats__scroll"
            role="region"
            aria-label="Placement statistics by branch"
            tabIndex={0}
          >
            <table className="branch-stats__table">
              <caption className="sr-only">
                Placement rate, offer records, companies and package figures (LPA, with the sample size n they are
                computed over) for every tracked branch of batch {data.batch}.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Branch</th>
                  <th scope="col">Placement rate</th>
                  <th scope="col" className="is-num">
                    Offers
                  </th>
                  <th scope="col" className="is-num">
                    Companies
                  </th>
                  <th scope="col" className="is-num">
                    Avg (LPA)
                  </th>
                  <th scope="col" className="is-num">
                    Median (LPA)
                  </th>
                  <th scope="col" className="is-num">
                    Highest (LPA)
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.branches.map((row) => (
                  <tr key={row.branch}>
                    <th scope="row">
                      <span className="branch-stats__branch">{row.branch}</span>
                    </th>
                    <td>
                      <span className="branch-stats__rate">
                        <span className="branch-stats__rate-text">
                          {count(row.placedstudents)} / {count(row.totalstudents)} ·{' '}
                          {percent(row.placementpercentage)}%
                        </span>
                        <span className="branch-stats__track" aria-hidden="true">
                          <span
                            className="branch-stats__fill"
                            style={{ width: `${barWidth(row.placementpercentage)}%` }}
                          />
                        </span>
                      </span>
                    </td>
                    <td className="is-num">{count(row.totaloffers)}</td>
                    <td className="is-num">{count(row.companies)}</td>
                    <td className="is-num">
                      <span className="branch-stats__pkg">{lpa(row.averagepackage)}</span>
                      <span className="branch-stats__n">n={count(row.studentswithpackage)}</span>
                    </td>
                    <td className="is-num">{lpa(row.medianpackage)}</td>
                    <td className="is-num">{lpa(row.highestpackage)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">All branches</th>
                  <td>
                    <span className="branch-stats__rate">
                      <span className="branch-stats__rate-text">
                        {count(summary.placedstudents)} / {count(summary.totalstudents)} ·{' '}
                        {percent(summary.placementpercentage)}%
                      </span>
                      <span className="branch-stats__track" aria-hidden="true">
                        <span
                          className="branch-stats__fill"
                          style={{ width: `${barWidth(summary.placementpercentage)}%` }}
                        />
                      </span>
                    </span>
                  </td>
                  <td className="is-num">{count(summary.totaloffers)}</td>
                  <td className="is-num">{count(summary.companies)}</td>
                  <td className="is-num">
                    <span className="branch-stats__pkg">{lpa(summary.averagepackage)}</span>
                    <span className="branch-stats__n">n={count(summary.studentswithpackage)}</span>
                  </td>
                  <td className="is-num">{lpa(summary.medianpackage)}</td>
                  <td className="is-num">{lpa(summary.highestpackage)}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="branch-stats__note">
            <Icon name="info" size={14} />
            Package figures are annual CTC in lakh. A row&apos;s <strong>n</strong> is how many of its placed
            students had an offer that actually stated a figure — average, median and highest are all computed over
            those n only. A branch with none shows a dash, never a zero.
          </p>

          {/* ---------- Distribution ---------- */}
          <h3 className="branch-stats__subtitle">Package distribution</h3>
          <p className="branch-stats__note">
            <Icon name="info" size={14} />
            JIIT&apos;s official bands, counted once per student on their best disclosed offer.
          </p>

          {bandOrder.length > 0 ? (
            <div
              className="branch-stats__scroll"
              role="region"
              aria-label="Package distribution by branch"
              tabIndex={0}
            >
              <table className="branch-stats__table branch-stats__table--bands">
                <caption className="sr-only">
                  Number of placed students in each package band, per branch.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Branch</th>
                    {bandOrder.map((band, index) => (
                      <th scope="col" className="is-num" key={`${band}-${index}`}>
                        <span className="branch-stats__th">
                          <BandSwatch band={band} />
                          {band}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.branches.map((row) => (
                    <tr key={row.branch}>
                      <th scope="row">{row.branch}</th>
                      {bandOrder.map((band, index) => (
                        <td className="is-num" key={`${band}-${index}`}>
                          {count(bandCount(row.distribution, band))}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">All branches</th>
                    {bandOrder.map((band, index) => (
                      <td className="is-num" key={`${band}-${index}`}>
                        {count(bandCount(summary.distribution, band))}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              </table>
            </div>
          ) : null}

          {/* ---------- Timeline ---------- */}
          <div className="branch-stats__chart-head">
            <h3 className="branch-stats__subtitle branch-stats__subtitle--inline">Offer timeline</h3>
            <label className="branch-stats__select">
              <span className="sr-only">Timeline branch</span>
              <select value={chartBranch} onChange={(event) => setChartBranch(event.target.value)}>
                <option value="">All branches</option>
                {data.branches.map((row) => (
                  <option value={row.branch} key={row.branch}>
                    {row.branch}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <p className="branch-stats__note">
            <Icon name="info" size={14} />
            Bucketed by the date the offer e-mail arrived — upper figure is students, lower figure is offer records.
          </p>

          {chartRows.length === 0 ? (
            <p className="branch-stats__empty">No offers recorded for this branch yet.</p>
          ) : (
            <ul className="branch-stats__bars">
              {chartRows.map((point) => {
                const label = parseMonth(point.month);
                const long = label?.long ?? point.month;
                const short = label?.short ?? point.month;
                return (
                  <li className="branch-stats__bar" key={point.month}>
                    <span className="sr-only">
                      {long}: {point.offers} offer{point.offers === 1 ? '' : 's'} from {point.students} student
                      {point.students === 1 ? '' : 's'}
                      {point.companies !== undefined
                        ? ` across ${point.companies} compan${point.companies === 1 ? 'y' : 'ies'}`
                        : ''}
                      .
                    </span>
                    <span className="branch-stats__bar-values" aria-hidden="true">
                      <span className="branch-stats__bar-students">{count(point.students)}</span>
                      <span className="branch-stats__bar-offers">{count(point.offers)}</span>
                    </span>
                    <span className="branch-stats__bar-track" aria-hidden="true">
                      <span
                        className="branch-stats__bar-shape"
                        style={{ height: `${barWidth((point.offers / maxOffers) * 100)}%` }}
                      />
                    </span>
                    <span className="branch-stats__bar-label" aria-hidden="true">
                      {short}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}

          <p className="branch-stats__foot">
            Generated {data.generatedat ? new Date(data.generatedat).toLocaleString() : '—'} from{' '}
            {count(summary.totaloffers)} offer records. Denominators are the published batch head-count, so a rate can
            never exceed 100%.
          </p>
        </>
      ) : null}
    </Card>
  );
}
