import { Card } from '../../components/ui/Card/Card';
import { ProgressBar } from '../../components/ui/ProgressBar/ProgressBar';
import { badgeColors, BRANCH_COLORS } from '../../components/placements/PlacedStudents/badgePalette';
import type { BranchStat, BranchStatsData } from '../../types/dashboard.types';
import { count, lpa, percent, shortBand } from './analyticsFormat';

/**
 * Analytics → Branches tab: one card per branch, mirroring the figures the
 * Branch-wise section of Placements shows so the two screens never disagree.
 *
 * COLOURS: each card's chip, rate bar and micro-visual use `BRANCH_COLORS` from
 * `components/placements/PlacedStudents/badgePalette.ts` — the same map the
 * branch badges use. Nothing is invented here.
 */

interface BranchesTabProps {
  data: BranchStatsData;
}

function BranchCard({ branch }: { branch: BranchStat }) {
  const colors = badgeColors(BRANCH_COLORS, branch.branch);
  const disclosed = (branch.finedistribution ?? []).filter((row) => row.band !== 'Not disclosed');
  const largestBand = disclosed.reduce<(typeof disclosed)[number] | null>(
    (best, row) => (best === null || row.offers > best.offers ? row : best),
    null,
  );
  const rate = branch.placementpercentage ?? 0;

  return (
    <Card as="article" className="branch-card" ariaLabel={`${branch.branch} placement statistics`}>
      <header className="branch-card__head">
        <span className="branch-card__chip" style={{ background: colors.bg, color: colors.text }}>
          {branch.branch}
        </span>
        <span className="branch-card__rate">{percent(rate)}</span>
      </header>

      {/* The rate is a genuine X / Y from this branch's own feed, so it gets
          the one shared progress bar — tinted with the branch's own colour. */}
      <span className="branch-card__bar" style={{ color: colors.text }}>
        <ProgressBar current={branch.placedstudents} total={branch.totalstudents} />
      </span>
      <p className="branch-card__placed">
        {count(branch.placedstudents)} of {count(branch.totalstudents)} students placed
      </p>

      <dl className="branch-card__figures">
        <div className="branch-card__figure">
          <dt>Offers</dt>
          <dd>{count(branch.totaloffers)}</dd>
        </div>
        <div className="branch-card__figure">
          <dt>Companies</dt>
          <dd>{count(branch.companies)}</dd>
        </div>
        <div className="branch-card__figure">
          <dt>Avg pkg</dt>
          <dd>{lpa(branch.averagepackage)}</dd>
        </div>
        <div className="branch-card__figure">
          <dt>Median pkg</dt>
          <dd>{lpa(branch.medianpackage)}</dd>
        </div>
        <div className="branch-card__figure">
          <dt>Highest pkg</dt>
          <dd>{lpa(branch.highestpackage)}</dd>
        </div>
        <div className="branch-card__figure">
          <dt>Disclosed</dt>
          <dd>{count(branch.studentswithpackage)}</dd>
        </div>
      </dl>

      {disclosed.length > 0 ? (
        <div className="branch-card__visual">
          <p className="branch-card__visual-note">
            Offers across {disclosed.length} disclosed bands
            {largestBand ? ` · largest ${shortBand(largestBand.band)} (${count(largestBand.offers)})` : ''}.
          </p>
        </div>
      ) : null}
    </Card>
  );
}

export function BranchesTab({ data }: BranchesTabProps) {
  const totals = data.totals;

  return (
    <div className="analytics-tab">
      <Card as="section" className="analytics-chart" ariaLabel="Branch totals">
        <header className="analytics-chart__head">
          <div>
            <h2 className="analytics-chart__title">Branch totals</h2>
            <p className="analytics-chart__sub">
              {count(totals.placedstudents)} of {count(totals.totalstudents)} students · {count(totals.totaloffers)}{' '}
              offers · {count(totals.companies)} companies.
            </p>
          </div>
        </header>
        <div className="branch-card__overall">
          <ProgressBar current={totals.placedstudents} total={totals.totalstudents} />
          <p className="branch-card__overall-note">
            {percent(totals.placementpercentage)} of the batch · average {lpa(totals.averagepackage)} LPA · median{' '}
            {lpa(totals.medianpackage)} LPA · highest {lpa(totals.highestpackage)} LPA.
          </p>
        </div>
      </Card>

      <section className="analytics-branch-grid" aria-label="Per-branch statistics">
        {data.branches.map((branch) => (
          <BranchCard key={branch.branch} branch={branch} />
        ))}
      </section>
    </div>
  );
}
