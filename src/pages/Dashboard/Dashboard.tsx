import { Link } from 'react-router-dom';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { Icon } from '../../components/common/Icon/Icon';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { Avatar } from '../../components/ui/Avatar/Avatar';
import { CalloutBanner } from '../../components/ui/CalloutBanner/CalloutBanner';
import { Card } from '../../components/ui/Card/Card';
import { DonutChart } from '../../components/ui/DonutChart/DonutChart';
import { PageHeader, SESSION_EYEBROW } from '../../components/ui/PageHeader/PageHeader';
import { HeroStat } from '../../components/ui/HeroStat/HeroStat';
import { Pill } from '../../components/ui/Pill/Pill';
import { StatCard } from '../../components/ui/StatCard/StatCard';
import { disclosedPackage, usePlacementSummary } from '../../hooks/usePlacementSummary';
import type { BranchTotal } from '../../hooks/usePlacementSummary';
import { formatDate, formatLpa, lpaFigure } from '../../utils/format';
import type { CompanyRow } from '../../types/dashboard.types';
import './Dashboard.scss';

/** Tint of a bar fill — one per package band, so the bands stay tellable apart. */
type BarTone = 'teal' | 'accent' | 'indigo' | 'green';

/** One horizontal bar: label · track · value. */
function BarRow({
  label,
  value,
  pct,
  tone = 'accent',
}: {
  label: string;
  value: string;
  pct: number;
  tone?: BarTone;
}) {
  return (
    <li className="dash-bars__row">
      <span className="dash-bars__label">{label}</span>
      <span className="dash-bars__track" aria-hidden="true">
        <span className={`dash-bars__fill dash-bars__fill--${tone}`} style={{ width: `${Math.max(pct, 2)}%` }} />
      </span>
      <span className="dash-bars__value">{value}</span>
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
 * How many branches the donut names before folding the tail into "Other".
 * Four keeps the legend to one short column (five rows beside a 148px ring)
 * while still naming every stream that carries a real share — the fifth-largest
 * branch on this feed is 4.3% of the total, so anything past four is noise a
 * reader has to decode instead of a fact they can use.
 */
const NAMED_BRANCHES = 4;

/**
 * Turn the hook's per-branch totals into donut slices that add back up to
 * `studentsPlaced` — the ONE invariant this panel must not break:
 *
 *   1. the top N branches, exactly as the feed spells them;
 *   2. everything below the cut, folded into "Other";
 *   3. any placed student whose row arrived with NO branch breakdown, in its
 *      own "Branch not stated" slice — never silently dropped, because a
 *      donut that quietly loses heads under-reports the total it sits under.
 *
 * On the live feed step 3 is empty (every placing row ships a breakdown that
 * sums to its own headcount), but the branch field is optional, so the rule
 * is implemented rather than assumed.
 */
function donutSegments(branchTotals: BranchTotal[], studentsPlaced: number) {
  const named = branchTotals.slice(0, NAMED_BRANCHES);
  const folded = branchTotals.slice(NAMED_BRANCHES).reduce((sum, entry) => sum + entry.students, 0);
  const stated = branchTotals.reduce((sum, entry) => sum + entry.students, 0);
  const unstated = Math.max(0, studentsPlaced - stated);

  return [
    ...named.map((entry) => ({ label: entry.branch, value: entry.students })),
    // Colours beyond the default palette are explicit so the tail cannot pick
    // up an accent hue and read as a branch of its own.
    ...(folded > 0 ? [{ label: 'Other', value: folded, color: 'var(--ui-muted)' }] : []),
    ...(unstated > 0
      ? [{ label: 'Branch not stated', value: unstated, color: 'var(--ui-tint-neutral-ink)' }]
      : []),
  ];
}

/**
 * Client home.
 *
 * A calm, celebratory summary rather than an analytical dashboard: an anchor
 * pair, four tiles, one record banner, a breakdown row, the package bands on
 * their own row, and a highlight strip. Every figure is summed from the same
 * read-only company-wise feed the Company-Wise screen uses — nothing here is
 * estimated, extrapolated or hand-entered.
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
  // Ranked list shows five, so the bars are scaled to the five a reader can
  // actually see — a sixth company outside the panel would only flatten them.
  const topFive = summary.topCompanies.slice(0, 5);
  const maxCompany = Math.max(1, ...topFive.map((row) => row.placedstudents || 0));
  const totalRead = summary.companiesRead;
  const highestLpa = lpaFigure(summary.highestPackage);
  const averageLpa = lpaFigure(summary.averagePackage);

  // The record behind the banner: the same row `highestPackage` came from,
  // so the company name, the headcount and the figure cannot disagree.
  const record = summary.topOffers[0] ?? null;
  const recordLpa = record ? lpaFigure(disclosedPackage(record)) : null;
  const recordPlaced = record?.placedstudents ?? 0;

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
            <Icon name="info" size={17} className="page-header__summary-icon" />
            <strong>{summary.studentsPlaced.toLocaleString()}</strong>
            <span>students have accepted offers from</span>
            <strong>{summary.companiesPlacing.toLocaleString()}</strong>
            <span>companies so far.</span>
          </>
        }
        tagline={
          <>
            <Icon name="eye" size={16} className="page-header__tagline-icon" />
            <span>
              JIIT Placements, <strong>Unfiltered.</strong> See What They Don&rsquo;t Want You Seeing.
            </span>
          </>
        }
      />

      {/* ---------------------------------------------------------------- */}
      {/* THE ANCHOR, split into two cards. The headline figure and the one  */}
      {/* true X / Y on this feed used to share one surface behind a         */}
      {/* hairline; standing them side by side gives each its own frame, so  */}
      {/* the eye lands on 420 first and on 46 / 92 as the qualifier it is. */}
      {/* Same StatCard vocabulary, same figures — 420, 46 and 92 are exactly */}
      {/* what the old block printed.                                        */}
      {/* ---------------------------------------------------------------- */}
      <div className="dash-hero">
        <HeroStat
          tint="accent"
          lead={{
            label: 'Students placed',
            value: summary.studentsPlaced.toLocaleString(),
            sublabel: `counted across ${totalRead.toLocaleString()} companies`,
            icon: 'users',
          }}
        />
        <HeroStat
          tint="accent"
          lead={{
            label: 'Companies that placed',
            value: summary.companiesPlacing.toLocaleString(),
            unit: `/ ${summary.companiesTotal.toLocaleString()}`,
            icon: 'building',
            progress: {
              current: summary.companiesPlacing,
              total: Math.max(summary.companiesTotal, summary.companiesPlacing),
            },
          }}
        />
      </div>

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
      {/* The record. A tile states 56 LPA; this states WHO paid it and how  */}
      {/* many students got it — the two facts the tile has no room for.     */}
      {/* Rendered only from a row that actually carries a disclosed offer,  */}
      {/* so an empty feed never prints a banner about nothing.              */}
      {/* ---------------------------------------------------------------- */}
      {record && recordLpa ? (
        <CalloutBanner
          icon="award"
          tone="amber"
          eyebrow="Highest package this season"
          title={`${record.company} · ${recordPlaced.toLocaleString()} ${
            recordPlaced === 1 ? 'student' : 'students'
          } placed`}
          figure={recordLpa}
          unit="LPA"
        />
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Breakdown — top companies (heads) beside the branch split. Both    */}
      {/* count students, so neither sits next to the package bands below,   */}
      {/* which measure money: the page never puts two different units in    */}
      {/* one row.                                                            */}
      {/* ---------------------------------------------------------------- */}
      <section className="dash-row" aria-label="Placement breakdown">
        <Card as="section" className="dash-panel" ariaLabel="Top 5 companies by students placed">
          <h2 className="dash-panel__title">Top 5 companies</h2>
          <p className="dash-panel__sub">Ranked by students placed — the same rows the Company-Wise screen lists.</p>
          <ol className="dash-bars">
            {topFive.map((row, index) => (
              <li className="dash-bars__row dash-bars__row--ranked" key={row.company}>
                {/* The <ol> already announces rank to assistive tech, so the
                    numeral is a visual echo only. */}
                <span className="dash-bars__rank" aria-hidden="true">
                  {index + 1}
                </span>
                <Avatar name={row.company} size={30} radius={8} />
                <Link className="dash-bars__link" to="/placements" title={row.company}>
                  {row.company}
                </Link>
                <span className="dash-bars__track" aria-hidden="true">
                  {/* Green: the page's placements hue — shared with the
                      "Highest package" tile and the top-offers strip below.
                      The money ramp also closes in green, but these two
                      charts never share a row, each is titled, and each bar
                      prints its own value, so the hue reads as one family
                      rather than as a shared axis. */}
                  <span
                    className="dash-bars__fill dash-bars__fill--green"
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

        <Card as="section" className="dash-panel" ariaLabel="Branch-wise placements">
          <h2 className="dash-panel__title">Branch-wise placements</h2>
          <p className="dash-panel__sub">
            Share of {summary.studentsPlaced.toLocaleString()} students placed.
          </p>
          {/* The ring is the illustration; the legend beside it and the
              visually-hidden table inside `DonutChart` are the data — so a
              phone or a screen reader gets every label and share without
              needing a hover target. */}
          <DonutChart
            ariaLabel="Students placed by branch"
            centerValue={summary.studentsPlaced.toLocaleString()}
            centerLabel="placed"
            segments={donutSegments(summary.branchTotals, summary.studentsPlaced)}
          />
        </Card>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Money — full width, on its own row. Splitting it from the two      */}
      {/* headcount panels above is what keeps the page's units legible:     */}
      {/* heads up top, rupees here, and no bar chart sharing a row with     */}
      {/* another chart on a different scale.                                */}
      {/* ---------------------------------------------------------------- */}
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
