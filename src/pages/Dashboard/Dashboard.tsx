import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { Icon } from '../../components/common/Icon/Icon';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { Avatar } from '../../components/ui/Avatar/Avatar';
import { Card } from '../../components/ui/Card/Card';
import { Pill } from '../../components/ui/Pill/Pill';
import { StatTile } from '../../components/ui/StatTile/StatTile';
import { disclosedPackage, usePlacementSummary } from '../../hooks/usePlacementSummary';
import { formatDate, formatLpa } from '../../utils/format';
import type { CompanyRow } from '../../types/dashboard.types';
import './Dashboard.scss';

/** One horizontal bar: label · track · value. */
function BarRow({ label, value, pct, prefix }: { label: string; value: string; pct: number; prefix?: ReactNode }) {
  return (
    <li className="dash-bars__row">
      <span className="dash-bars__label">{label}</span>
      <span className="dash-bars__track" aria-hidden="true">
        <span className="dash-bars__fill" style={{ width: `${Math.max(pct, 2)}%` }} />
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
        <header className="dash-head">
          <p className="dash-head__eyebrow">Placement cell</p>
          <h1 className="dash-head__title">Dashboard</h1>
        </header>
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

  return (
    <div className="page dashboard">
      <header className="dash-head">
        <p className="dash-head__eyebrow">Placement cell · session 2026–27</p>
        <h1 className="dash-head__title">Dashboard</h1>
        <p className="dash-head__sub">
          {summary.studentsPlaced.toLocaleString()} students have accepted offers from{' '}
          {summary.companiesPlacing.toLocaleString()} companies so far.
        </p>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Hero row — six statistics (the two coverage tiles are additive;   */}
      {/* the original four are untouched)                                  */}
      {/* ---------------------------------------------------------------- */}
      <section className="dash-hero" aria-label="Placement highlights">
        <StatTile
          label="Students placed"
          value={summary.studentsPlaced.toLocaleString()}
          hint={`counted across ${totalRead.toLocaleString()} companies`}
          icon="users"
          tone="accent"
        />
        <StatTile
          label="Companies that placed"
          value={summary.companiesPlacing.toLocaleString()}
          hint={`of ${summary.companiesTotal.toLocaleString()} companies on file`}
          icon="building"
          tone="neutral"
        />
        <StatTile
          label="Streams covered"
          value={summary.streamsCovered.toLocaleString()}
          hint="distinct branches with at least one offer"
          icon="layers"
          tone="neutral"
        />
        <StatTile
          label="Campuses"
          value={summary.campusesCovered.toLocaleString()}
          hint="distinct campuses with at least one offer"
          icon="pin"
          tone="neutral"
        />
        <StatTile
          label="Highest package"
          value={formatLpa(summary.highestPackage) ?? '—'}
          hint="best disclosed offer among placed students"
          icon="award"
          tone="green"
        />
        <StatTile
          label="Average package"
          value={formatLpa(summary.averagePackage) ?? '—'}
          hint="disclosed packages, weighted by students placed"
          icon="rupee"
          tone="amber"
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
            {summary.bands.map((band) => (
              <BarRow
                key={band.label}
                label={band.label}
                value={band.students.toLocaleString()}
                pct={Math.round((band.students / maxBand) * 100)}
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
                  <span
                    className="dash-bars__fill"
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
