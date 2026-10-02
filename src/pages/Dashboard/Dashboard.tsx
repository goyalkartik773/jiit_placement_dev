import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { Icon } from '../../components/common/Icon/Icon';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { Avatar } from '../../components/ui/Avatar/Avatar';
import { Card } from '../../components/ui/Card/Card';
import { PageHeader, SESSION_EYEBROW } from '../../components/ui/PageHeader/PageHeader';
import { HeroStat } from '../../components/ui/HeroStat/HeroStat';
import { Pill } from '../../components/ui/Pill/Pill';
import { StatCard } from '../../components/ui/StatCard/StatCard';
import { disclosedPackage, usePlacementSummary } from '../../hooks/usePlacementSummary';
import { formatDate, formatLpa, lpaFigure } from '../../utils/format';
import type { CompanyRow } from '../../types/dashboard.types';
import './Dashboard.scss';

/** Tint of a bar fill — one per package band, so the bands stay tellable apart. */
type BarTone = 'teal' | 'accent' | 'indigo' | 'green' | 'violet';

/** One horizontal bar: label · track · value. */
function BarRow({
  label,
  value,
  pct,
  prefix,
  tone = 'accent',
}: {
  label: string;
  value: string;
  pct: number;
  prefix?: ReactNode;
  tone?: BarTone;
}) {
  return (
    <li className="dash-bars__row">
      <span className="dash-bars__label">{label}</span>
      <span className="dash-bars__track" aria-hidden="true">
        <span className={`dash-bars__fill dash-bars__fill--${tone}`} style={{ width: `${Math.max(pct, 2)}%` }} />
      </span>
      <span className="dash-bars__value">
        {prefix}
        {value}
      </span>
    </li>
  );
}

/** Company row of the highlight strips: avatar · name · the number. */
function CompanyLine({ row, meta, tone }: { row: CompanyRow; meta: string; tone: 'accent' | 'green' }) {
  return (
    <li className="dash-highlight__item">
      <Avatar name={row.company} size={38} radius={10} />
      <span className="dash-highlight__identity">
        <span className="dash-highlight__name" title={row.company}>
          {row.company}
        </span>
        <span className="dash-highlight__meta">{meta}</span>
      </span>
      <span className={`dash-highlight__figure dash-highlight__figure--${tone}`}>
        {tone === 'green' ? (formatLpa(disclosedPackage(row)) ?? '—') : row.placedstudents.toLocaleString()}
      </span>
    </li>
  );
}

/**
 * Client home.
 *
 * A calm, celebratory summary rather than an analytical dashboard: four hero
 * numbers, one breakdown chart and a highlight strip. Every figure is summed
 * from the same read-only company-wise feed the Company-Wise screen uses —
 * nothing here is estimated, extrapolated or hand-entered.
 */
export function Dashboard() {
  const { summary, loading, error, reload } = usePlacementSummary();

  if (error && !summary) {
    return (
      <div className="page dashboard">
        <ErrorState title="Could not load the dashboard" message={error.message} onRetry={reload} />
      </div>
    );
  }

  if (loading || !summary) {
    return (
      <div className="page dashboard">
        <ListSkeleton count={4} label="Loading placements" />
      </div>
    );
  }

  if (summary.studentsPlaced === 0) {
    return (
      <div className="page dashboard">
        {/* Same `PageHeader` as the populated view — the empty state used to
            hand-roll a second header block whose CSS no longer exists. */}
        <PageHeader eyebrow={SESSION_EYEBROW} title="Dashboard" />
        <EmptyState
          title="No placements recorded yet"
          description="The dashboard lights up as soon as the first offer is matched to a student."
        />
      </div>
    );
  }

  const maxBand = Math.max(1, ...summary.bands.map((band) => band.students));
  const maxCompany = Math.max(1, ...summary.topCompanies.map((row) => row.placedstudents || 0));
  const totalRead = summary.companiesRead;
  const highestLpa = lpaFigure(summary.highestPackage);
  const averageLpa = lpaFigure(summary.averagePackage);

  return (
    <div className="page dashboard">
      {/* The one sentence that answers "how are we doing" — promoted from a
          muted sub-line to a stated summary. Same two figures, same feed;
          nothing here is computed or rounded differently. Rendered by the
          shared `PageHeader`, so Analytics prints an identical block. */}
      <PageHeader
        eyebrow={SESSION_EYEBROW}
        title="Dashboard"
        summary={
          <>
            <strong>{summary.studentsPlaced.toLocaleString()}</strong>
            <span>students have accepted offers from</span>
            <strong>{summary.companiesPlacing.toLocaleString()}</strong>
            <span>companies so far.</span>
          </>
        }
      />

      {/* ---------------------------------------------------------------- */}
      {/* THE ANCHOR. Six tiles of equal weight gave the eye nowhere to      */}
      {/* land, so the headline figure is promoted to display scale and the  */}
      {/* one true X / Y on this feed stands beside it behind a hairline.    */}
      {/* Same StatCard vocabulary at a larger size — nothing is derived:    */}
      {/* 420, 46 and 91 are the exact figures the old tiles printed.        */}
      {/* ---------------------------------------------------------------- */}
      <HeroStat
        tint="accent"
        lead={{
          label: 'Students placed',
          value: summary.studentsPlaced.toLocaleString(),
          sublabel: `counted across ${totalRead.toLocaleString()} companies`,
          icon: 'users',
        }}
        support={{
          label: 'Companies that placed',
          value: summary.companiesPlacing.toLocaleString(),
          sublabel: `of ${summary.companiesTotal.toLocaleString()} companies on file`,
          icon: 'building',
          progress: {
            current: summary.companiesPlacing,
            total: Math.max(summary.companiesTotal, summary.companiesPlacing),
          },
        }}
      />

      {/* ---------------------------------------------------------------- */}
      {/* The four supporting figures, still the loose tinted tiles that     */}
      {/* are this page's identity. Four, not six — the hero carries the     */}
      {/* other two, so the grid is stamped with its count and never strands */}
      {/* a tile on a row of its own.                                        */}
      {/* ---------------------------------------------------------------- */}
      <section className="ui-stat-card-row" data-cells={4} aria-label="Placement highlights">
        {/* None of these four is an X / Y: this feed states no denominator
            for a stream, a campus or a package — see
            components/ui/StatCard/metricKind.ts for the rule. */}
        <StatCard
          label="Streams covered"
          value={summary.streamsCovered.toLocaleString()}
          sublabel="distinct branches with at least one offer"
          icon="layers"
          tint="violet"
        />
        {/* No "campuses total" exists in this feed, so the count stays a
            plain value — a bar would need a denominator nothing states. */}
        <StatCard
          label="Campuses"
          value={summary.campusesCovered.toLocaleString()}
          sublabel="distinct campuses with at least one offer"
          icon="pin"
          tint="teal"
        />
        <StatCard
          label="Highest package"
          /* `lpaFigure` splits the number off `formatLpa` so "LPA" can print
             as its own muted span and "56 LPA" can never wrap mid-figure. */
          value={highestLpa ?? '—'}
          unit={highestLpa ? 'LPA' : undefined}
          sublabel="best disclosed offer among placed students"
          icon="award"
          tint="green"
        />
        <StatCard
          label="Average package"
          value={averageLpa ?? '—'}
          unit={averageLpa ? 'LPA' : undefined}
          sublabel="disclosed packages, weighted by students placed"
          icon="rupee"
          tint="amber"
        />
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Breakdown — package bands + top companies                        */}
      {/* ---------------------------------------------------------------- */}
      <section className="dash-row" aria-label="Placement breakdown">
        <Card as="section" className="dash-panel" ariaLabel="Placements by package band">
          <h2 className="dash-panel__title">Placements by package band</h2>
          <p className="dash-panel__sub">Students placed, grouped by the disclosed package of their company.</p>
          <ul className="dash-bars">
            {summary.bands.map((band, index) => (
              <BarRow
                key={band.label}
                label={band.label}
                value={band.students.toLocaleString()}
                pct={Math.round((band.students / maxBand) * 100)}
                /* Ascending ramp: the four bands step teal → accent → indigo →
                   green as the package rises, so a colour alone locates a bar
                   on the scale. Green is the same green as the "Highest
                   package" tile — the top band and the record are the idea. */
                tone={(['teal', 'accent', 'indigo', 'green'] as const)[index] ?? 'accent'}
              />
            ))}
          </ul>
          {summary.undisclosedStudents > 0 ? (
            <p className="dash-panel__foot">
              {summary.undisclosedStudents.toLocaleString()} placed{' '}
              {summary.undisclosedStudents === 1 ? 'student sits' : 'students sit'} with no disclosed package and are
              not counted in a band.
            </p>
          ) : null}
        </Card>

        <Card as="section" className="dash-panel" ariaLabel="Top companies by students placed">
          <h2 className="dash-panel__title">Top companies</h2>
          <p className="dash-panel__sub">Ranked by students placed — the same rows the Company-Wise screen lists.</p>
          <ol className="dash-bars">
            {summary.topCompanies.map((row) => (
              <li className="dash-bars__row dash-bars__row--company" key={row.company}>
                <Avatar name={row.company} size={30} radius={8} />
                <Link className="dash-bars__link" to="/placements" title={row.company}>
                  {row.company}
                </Link>
                <span className="dash-bars__track" aria-hidden="true">
                  {/* Violet, not accent: this chart counts heads while the band
                      chart measures money, so the two never read as one scale. */}
                  <span
                    className="dash-bars__fill dash-bars__fill--violet"
                    style={{ width: `${Math.max(Math.round(((row.placedstudents || 0) / maxCompany) * 100), 2)}%` }}
                  />
                </span>
                <span className="dash-bars__value">{(row.placedstudents || 0).toLocaleString()}</span>
              </li>
            ))}
          </ol>
          <Link className="dash-panel__more" to="/placements">
            See every company
            <Icon name="chevron-right" size={15} />
          </Link>
        </Card>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Highlight strip — recently placed + top offers                   */}
      {/* ---------------------------------------------------------------- */}
      <section className="dash-row dash-row--strip" aria-label="Recent and top offers">
        <Card as="section" className="dash-highlight" ariaLabel="Recently placed">
          <div className="dash-highlight__head">
            <h2 className="dash-highlight__title">Recently placed</h2>
            <Pill tone="accent">Newest offers first</Pill>
          </div>
          {summary.recentCompanies.length === 0 ? (
            <p className="dash-highlight__empty">No dated offers yet.</p>
          ) : (
            <ul className="dash-highlight__list">
              {summary.recentCompanies.map((row) => (
                <CompanyLine
                  key={row.company}
                  row={row}
                  tone="accent"
                  meta={`Last offer ${formatDate(row.lastplacedat)}`}
                />
              ))}
            </ul>
          )}
        </Card>

        <Card as="section" className="dash-highlight" ariaLabel="Top offers">
          <div className="dash-highlight__head">
            <h2 className="dash-highlight__title">Top offers</h2>
            <Pill tone="green">Highest packages</Pill>
          </div>
          {summary.topOffers.length === 0 ? (
            <p className="dash-highlight__empty">No disclosed packages yet.</p>
          ) : (
            <ul className="dash-highlight__list">
              {summary.topOffers.map((row) => (
                <CompanyLine
                  key={row.company}
                  row={row}
                  tone="green"
                  meta={`${row.placedstudents.toLocaleString()} placed`}
                />
              ))}
            </ul>
          )}
        </Card>
      </section>

      <p className="dash-footnote">
        Every figure is summed from the same company-wise feed the Company-Wise screen lists, so a student with offers
        from more than one company is counted once per company. Packages are the disclosed figures returned by that
        feed; offers with no published package are excluded from the average and the highest figure. Head to{' '}
        <Link to="/placements">Company-Wise Placement</Link> for the full breakdown, or{' '}
        <Link to="/email-notices">Email Notices</Link> for the source emails.
      </p>
    </div>
  );
}
