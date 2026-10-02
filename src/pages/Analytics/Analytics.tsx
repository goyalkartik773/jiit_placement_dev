import { useEffect, useMemo, useState } from 'react';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { PageHeader, SESSION_EYEBROW } from '../../components/ui/PageHeader/PageHeader';
import { HeroStat } from '../../components/ui/HeroStat/HeroStat';
import { MetricStrip, type MetricStripItem } from '../../components/ui/MetricStrip/MetricStrip';
import { TabBar, type TabDescriptor } from '../../components/ui/TabBar/TabBar';
import { usePlacementSummary } from '../../hooks/usePlacementSummary';
import { fetchBranchStats } from '../../services/placementService';
import { isAbortError } from '../../services/apiClient';
import type { BranchStatsData } from '../../types/dashboard.types';
import { BranchesTab } from './BranchesTab';
import { CompaniesTab } from './CompaniesTab';
import { DistributionTab } from './DistributionTab';
import { TimelineTab } from './TimelineTab';
import { count, lpa, percent } from './analyticsFormat';
import './Analytics.scss';

/**
 * Analytics — the read-only reporting screen.
 *
 * DATA: one fetch of `GET /api/placements/branch-stats` supplies every number on
 * this page except the two company-feed denominators, which come from
 * `usePlacementSummary()` (the same hook the Dashboard already uses, so the two
 * screens can never disagree about what "companies" means).
 *
 * COLOURS: only tokens from `styles/_ui.scss` (the six stat tints plus
 * `--ui-accent`) and `BRANCH_COLORS` from `badgePalette.ts` (inside the tabs).
 * No colour literal is declared on this page.
 */

type TabId = 'branches' | 'companies' | 'distribution' | 'timeline' | 'on-campus';

const TABS: TabDescriptor[] = [
  { id: 'branches', label: 'Branches', icon: 'layers' },
  { id: 'companies', label: 'Companies', icon: 'building' },
  { id: 'distribution', label: 'Distribution', icon: 'chart' },
  { id: 'timeline', label: 'Timeline', icon: 'calendar' },
  {
    id: 'on-campus',
    label: 'On campus',
    icon: 'pin',
    disabled: true,
    badge: 'soon',
    title: 'On-campus placements are not separated in the feed yet.',
  },
];

export function Analytics() {
  const [data, setData] = useState<BranchStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tab, setTab] = useState<TabId>('branches');

  const { summary } = usePlacementSummary();

  useEffect(() => {
    const controller = new AbortController();
    let live = true;

    setLoading(true);
    setError(null);
    fetchBranchStats(controller.signal)
      .then((result) => {
        if (!live) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (!live || controller.signal.aborted || isAbortError(caught)) return;
        setError(caught as Error);
        setLoading(false);
      });

    return () => {
      live = false;
      controller.abort();
    };
  }, []);

  const totals = data?.totals;

  /**
   * The two headline figures — the placement rate and the company count —
   * read straight off `totals` / `summary` and handed to `HeroStat`. The four
   * compensation/offer figures go to the strip below, so the screen has an
   * anchor instead of six equally-weighted boxes.
   */
  const hero = useMemo(() => {
    if (!totals) return null;
    const companies = summary?.companiesPlacing ?? null;

    return {
      lead: {
        label: 'Placement rate',
        // `placementpercentage` arrives rounded to 2dp from SQL — printed as
        // is, never recomputed here. It is the one figure a placement screen
        // is judged on, which is why it gets display scale.
        value: percent(totals.placementpercentage),
        sublabel: `${count(totals.placedstudents)} of ${count(totals.totalstudents)} students placed`,
        icon: 'users' as const,
        progress: { current: totals.placedstudents, total: totals.totalstudents },
      },
      support: {
        label: 'Companies',
        value: count(totals.companies),
        unit: companies ? `/ ${count(companies)}` : undefined,
        sublabel: companies ? 'hired this batch / any placement' : 'hired from this batch',
        icon: 'building' as const,
        progress: companies ? { current: totals.companies, total: companies } : undefined,
      },
    };
  }, [summary?.companiesPlacing, totals]);

  /**
   * Four supporting figures — every one read straight off `totals`, none
   * derived. `unit` carries whatever trails the number ("LPA"), so the figure
   * itself can never wrap.
   */
  const tiles = useMemo<MetricStripItem[] | null>(() => {
    if (!totals) return null;
    const avgLpa = lpa(totals.averagepackage);
    const medianLpa = lpa(totals.medianpackage);
    const highestLpa = lpa(totals.highestpackage);

    // None of these four plots an X / Y — they are standalone figures, so
    // none gets the shared progress bar (rule in StatCard/metricKind.ts).
    return [
      {
        key: 'avg',
        label: 'Average package',
        value: avgLpa ?? '—',
        unit: avgLpa ? 'LPA' : undefined,
        sublabel: 'mean of disclosed offers',
        tint: 'amber' as const,
        icon: 'rupee' as const,
        progress: undefined,
      },
      {
        key: 'median',
        label: 'Median package',
        value: medianLpa ?? '—',
        unit: medianLpa ? 'LPA' : undefined,
        sublabel: 'middle of disclosed offers',
        tint: 'violet' as const,
        icon: 'sort' as const,
        progress: undefined,
      },
      {
        key: 'highest',
        label: 'Highest package',
        value: highestLpa ?? '—',
        unit: highestLpa ? 'LPA' : undefined,
        sublabel: 'best offer recorded',
        tint: 'green' as const,
        icon: 'award' as const,
        progress: undefined,
      },
      {
        key: 'offers',
        label: 'Total offers',
        value: count(totals.totaloffers),
        unit: undefined,
        sublabel: `${count(totals.placedstudents)} unique students`,
        tint: 'teal' as const,
        icon: 'layers' as const,
        progress: undefined,
      },
    ];
  }, [totals]);

  const panel = (() => {
    if (!data) return null;
    switch (tab) {
      case 'companies':
        return (
          <CompaniesTab
            summary={summary}
            batchCompanies={data.totals.companies}
            batchOffers={data.totals.totaloffers}
          />
        );
      case 'distribution':
        return <DistributionTab data={data} />;
      case 'timeline':
        return <TimelineTab data={data} />;
      case 'on-campus':
        return (
          <p className="analytics-empty-note">
            On-campus placements are not separated in the feed yet — this view is coming soon.
          </p>
        );
      case 'branches':
      default:
        return <BranchesTab data={data} />;
    }
  })();

  return (
    <div className="page analytics-page">
      {/* The report masthead: no accent card, no left bar — a plain meta line
          closed by a hairline. Dashboard keeps the accent card, so the two
          pages announce themselves differently from the very first line. */}
      <PageHeader
        variant="report"
        eyebrow={SESSION_EYEBROW}
        title="Analytics"
        summary={
          loading && !data ? (
            'Loading branch statistics…'
          ) : totals ? (
            <>
              <span>
                Batch <strong>{data?.batch}</strong>
              </span>
              <span aria-hidden="true">·</span>
              <span>
                <strong>{count(totals.placedstudents)}</strong> of {count(totals.totalstudents)} placed
              </span>
              <span aria-hidden="true">·</span>
              <span>
                <strong>{count(totals.totaloffers)}</strong> offers
              </span>
              <span aria-hidden="true">·</span>
              <span>
                average <strong>{lpa(totals.averagepackage) ?? '—'}</strong> LPA
              </span>
            </>
          ) : (
            'Branch statistics are unavailable.'
          )
        }
      />

      {error && !data ? (
        <ErrorState
          title="Could not load analytics"
          message={error.message || 'Branch statistics request failed'}
          onRetry={() => window.location.reload()}
        />
      ) : null}

      {!data && !error ? <ListSkeleton count={4} label="Loading analytics" /> : null}

      {/* THE ANCHOR. White surface, hairline frame, identity from the accent
          — the report framing that matches this page's header, and the exact
          complement of the Dashboard's tinted hero. The rate is the one figure
          a placement screen is judged on, so it is the one at display scale;
          the 26.1% and the 345 / 1,322 were already printed here, just at
          tile size with nowhere to look first. */}
      {hero ? <HeroStat variant="report" tint="accent" lead={hero.lead} support={hero.support} /> : null}

      {/* Four supporting figures as ONE divided panel — the composition this
          page owns. The Dashboard keeps its loose tinted tiles below its own
          hero, so the two screens stay siblings, not copies. */}
      {tiles ? <MetricStrip items={tiles} ariaLabel="Package and offer figures" /> : null}

      {totals ? (
        <div className="analytics-banner" role="note">
          <p>
            Figures cover the <strong>{data?.batch}</strong> graduating batch only, from the branch-wise feed.
            Company counts drawn from the Company-Wise feed cover every batch and are labelled where they appear.
            Package figures are annual CTC in LPA; offers with no disclosed CTC are excluded from averages, medians
            and the highest figure rather than counted as zero.
          </p>
        </div>
      ) : null}

      {data ? (
        <>
          <TabBar tabs={TABS} value={tab} onChange={(next) => setTab(next as TabId)} label="Analytics views" />
          <div
            className="analytics-panel"
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
            tabIndex={-1}
          >
            {panel}
          </div>
        </>
      ) : null}
    </div>
  );
}
