import { Link } from 'react-router-dom';
import { Card } from '../../components/ui/Card/Card';
import { Icon } from '../../components/common/Icon/Icon';
import { Avatar } from '../../components/ui/Avatar/Avatar';
import { Pill } from '../../components/ui/Pill/Pill';
import { MetricStrip } from '../../components/ui/MetricStrip/MetricStrip';
import { disclosedPackage, type PlacementSummary } from '../../hooks/usePlacementSummary';
import { formatLpa } from '../../utils/format';
import { count } from './analyticsFormat';

/**
 * Analytics → Companies tab.
 *
 * This deliberately does NOT rebuild the Company-Wise Placement screen: that
 * page already owns search, sort, filters, pagination and the full row detail,
 * all driven by a separate feed. This tab is a read-only roll-up plus a link.
 *
 * COLOURS: only the StatCard tints from `styles/_ui.scss` (fill, rail, icon)
 * plus the shared Badge component's own palette. No surface here invents a
 * colour.
 */

interface CompaniesTabProps {
  summary: PlacementSummary | null;
  /** Companies that placed at least one student in THIS batch (branch-stats feed). */
  batchCompanies: number;
  /** Offers in this batch (branch-stats feed). */
  batchOffers: number;
}

export function CompaniesTab({ summary, batchCompanies, batchOffers }: CompaniesTabProps) {
  const top = summary?.topCompanies.slice(0, 10) ?? [];
  // `count(null)` renders "0", which would assert "no companies" while the
  // feed is still in flight. Hold the dash until the hook resolves.
  const pending = summary === null;

  return (
    <div className="analytics-tab">
      {/* Four-cell strip, same composition as the rest of Analytics. All four
          are standalone counts, so none of them takes a progress bar (no X / Y
          is printed here). */}
      <MetricStrip
        ariaLabel="Company totals"
        items={[
          {
            key: 'batch-companies',
            label: 'Hired from this batch',
            value: count(batchCompanies),
            sublabel: 'companies that extended at least one offer',
            icon: 'building',
            tint: 'accent',
          },
          {
            key: 'batch-offers',
            label: 'Offers made',
            value: count(batchOffers),
            sublabel: 'by those companies, this graduating batch',
            icon: 'layers',
            tint: 'teal',
          },
          {
            key: 'placing',
            label: 'Any placement on record',
            value: pending ? '—' : count(summary.companiesPlacing),
            sublabel: 'companies with at least one placed student',
            icon: 'users',
            tint: 'indigo',
            ariaBusy: pending,
          },
          {
            key: 'in-feed',
            label: 'Companies in feed',
            value: pending ? '—' : count(summary.companiesTotal),
            sublabel: 'across every batch on file',
            icon: 'checklist',
            tint: 'violet',
            ariaBusy: pending,
          },
        ]}
      />

      <Card as="section" className="analytics-chart" ariaLabel="Top companies by students placed">
        <header className="analytics-chart__head">
          <div>
            <h2 className="analytics-chart__title">Top companies</h2>
            <p className="analytics-chart__sub">Ranked by students placed across all batches.</p>
          </div>
          <Link className="analytics-chart__more" to="/placements">
            Open Company-Wise Placement
            <Icon name="external-link" size={14} />
          </Link>
        </header>

        {top.length === 0 ? (
          <p className="analytics-empty-note">
            {pending ? 'Company data is still loading.' : 'No companies in the feed yet.'}
          </p>
        ) : (
          <ol className="analytics-companies">
            {top.map((company, index) => {
              // `disclosedPackage()` returns annual INR; `formatLpa()` divides by
              // 100000 — unlike the branch-stats feed, which is already in LPA.
              const rupees = disclosedPackage(company);
              return (
                <li className="analytics-companies__row" key={company.company ?? index}>
                  <span className="analytics-companies__rank" aria-hidden="true">
                    {index + 1}
                  </span>
                  <Avatar name={company.company} size={32} radius={9} />
                  <span className="analytics-companies__name">{company.company || 'Unnamed company'}</span>
                  <Pill>{count(company.placedstudents)} placed</Pill>
                  <span className="analytics-companies__pkg">{rupees > 0 ? formatLpa(rupees) : '—'}</span>
                </li>
              );
            })}
          </ol>
        )}
      </Card>

      <p className="analytics-footnote">
        Company figures come from the Company-Wise feed, which counts every batch; batch figures above come from the
        branch-wise feed scoped to this graduating batch. The two are not interchangeable.
      </p>
    </div>
  );
}
