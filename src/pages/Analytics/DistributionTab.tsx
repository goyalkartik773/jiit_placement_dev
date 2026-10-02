import { useMemo, useState } from 'react';
import { Card } from '../../components/ui/Card/Card';
import { MetricStrip } from '../../components/ui/MetricStrip/MetricStrip';
import { badgeColors, BRANCH_COLORS } from '../../components/placements/PlacedStudents/badgePalette';
import type { BranchStat, BranchStatsData } from '../../types/dashboard.types';
import { LineChart, OVERALL_DASH, type ChartSeries } from './LineChart';
import { bandFloor, count, shortBand } from './analyticsFormat';

/**
 * Analytics → Distribution tab.
 *
 * COLOURS: every series colour comes from `badgePalette.ts` (`BRANCH_COLORS`,
 * the same map the branch badges use) or from `--ui-accent` in
 * `src/styles/_ui.scss` for the all-branches reference line. Nothing is
 * invented here.
 *
 * Y unit is OFFERS (the endpoint counts offers per fine band), not distinct
 * students — the two would differ wherever a student holds two offers.
 */

interface DistributionTabProps {
  data: BranchStatsData;
}

/** One dash pattern per branch index so similarly-coloured lines stay apart. */
const BRANCH_DASH: Record<string, string> = {
  CSE: '0', // solid — the largest branch
  ECE: '6 3',
  IT: '2 3',
  BT: '9 4 2 4',
  'Intg. MTech': '1 3',
  'EC-ACT': '12 4',
  'EE-VLSI': '4 3 1 3',
};

/** Strip the full band name down to an axis-friendly token. */
function axisLabel(band: string): string {
  return band === 'Not disclosed' ? 'Not disclosed' : shortBand(band);
}

export function DistributionTab({ data }: DistributionTabProps) {
  const bands = data.totals.finedistribution ?? [];
  const categories = bands.map((band) => axisLabel(band.band));

  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<'area' | 'line'>('area');
  const [layout, setLayout] = useState<'combined' | 'individual'>('combined');

  const toggleBranch = (branch: string) =>
    setSelected((current) =>
      current.includes(branch) ? current.filter((name) => name !== branch) : [...current, branch],
    );

  const byName = useMemo(() => {
    const map = new Map<string, BranchStat>();
    for (const branch of data.branches) map.set(branch.branch, branch);
    return map;
  }, [data.branches]);

  /**
   * The all-branches reference series — dashed accent, identical in both
   * layouts. It needs a fill of its own: without one the Area/Line toggle
   * would appear to do nothing until the user picked a branch, because the
   * overall line is the only series on screen.
   */
  const overallSeries: ChartSeries = {
    key: '__overall__',
    label: 'All branches',
    stroke: 'var(--ui-accent)',
    fill: 'var(--ui-accent-soft)',
    dash: OVERALL_DASH,
    strokeWidth: 2.5,
    values: bands.map((band) => band.offers),
  };

  const branchSeries = (branch: BranchStat): ChartSeries => {
    const colors = badgeColors(BRANCH_COLORS, branch.branch);
    const own = branch.finedistribution ?? [];
    // Fall back to the total's band order when a branch sends no fine rows.
    const values = bands.map((band) => own.find((row) => row.band === band.band)?.offers ?? 0);
    return {
      key: branch.branch,
      label: branch.branch,
      stroke: colors.text,
      fill: colors.bg,
      dash: BRANCH_DASH[branch.branch] ?? '6 3',
      values,
    };
  };

  /** `Array.prototype.filter(Boolean)` does NOT narrow in TS — this does. */
  const pickedBranches = (): BranchStat[] =>
    selected.map((name) => byName.get(name)).filter((branch): branch is BranchStat => branch !== undefined);

  const combinedSeries = [overallSeries, ...pickedBranches().map(branchSeries)];
  const individualSeries = pickedBranches().map((branch) => ({ reference: overallSeries, own: branchSeries(branch) }));

  // ---- Summary cards (all from the same finedistribution rows as the chart) ----
  const disclosedRows = bands.filter((band) => band.band !== 'Not disclosed');
  const totalOffers = bands.reduce((sum, band) => sum + band.offers, 0);
  const disclosedOffers = disclosedRows.reduce((sum, band) => sum + band.offers, 0);
  const mostCommon = disclosedRows.reduce<(typeof disclosedRows)[number] | null>(
    (best, band) => (best === null || band.offers > best.offers ? band : best),
    null,
  );
  const tenPlusRows = disclosedRows.filter((band) => (bandFloor(band.band) ?? 0) >= 10);
  const tenPlusOffers = tenPlusRows.reduce((sum, band) => sum + band.offers, 0);

  const legend = combinedSeries;

  return (
    <div className="analytics-tab">
      <div className="analytics-controls" role="group" aria-label="Distribution chart controls">
        <div className="analytics-controls__group">
          <span className="analytics-controls__label" id="dist-branch-label">
            Branches
          </span>
          <div className="analytics-controls__chips" role="group" aria-labelledby="dist-branch-label">
            {data.branches.map((branch) => {
              const colors = badgeColors(BRANCH_COLORS, branch.branch);
              const active = selected.includes(branch.branch);
              return (
                <button
                  key={branch.branch}
                  type="button"
                  className={`analytics-chip${active ? ' is-active' : ''}`}
                  aria-pressed={active}
                  onClick={() => toggleBranch(branch.branch)}
                  style={
                    active
                      ? ({ '--chip-bg': colors.bg, '--chip-ink': colors.text } as React.CSSProperties)
                      : undefined
                  }
                >
                  <span className="analytics-chip__dot" aria-hidden="true" style={{ background: colors.text }} />
                  {branch.branch}
                </button>
              );
            })}
            {selected.length > 0 ? (
              <button type="button" className="analytics-chip analytics-chip--clear" onClick={() => setSelected([])}>
                Clear
              </button>
            ) : null}
          </div>
        </div>

        <div className="analytics-controls__group">
          <span className="analytics-controls__label" id="dist-mode-label">
            Style
          </span>
          <div className="analytics-controls__seg" role="group" aria-labelledby="dist-mode-label">
            <button
              type="button"
              className={`analytics-seg${mode === 'area' ? ' is-active' : ''}`}
              aria-pressed={mode === 'area'}
              onClick={() => setMode('area')}
            >
              Area
            </button>
            <button
              type="button"
              className={`analytics-seg${mode === 'line' ? ' is-active' : ''}`}
              aria-pressed={mode === 'line'}
              onClick={() => setMode('line')}
            >
              Line
            </button>
          </div>
        </div>

        <div className="analytics-controls__group">
          <span className="analytics-controls__label" id="dist-layout-label">
            Layout
          </span>
          <div className="analytics-controls__seg" role="group" aria-labelledby="dist-layout-label">
            <button
              type="button"
              className={`analytics-seg${layout === 'combined' ? ' is-active' : ''}`}
              aria-pressed={layout === 'combined'}
              onClick={() => setLayout('combined')}
            >
              Combined
            </button>
            <button
              type="button"
              className={`analytics-seg${layout === 'individual' ? ' is-active' : ''}`}
              aria-pressed={layout === 'individual'}
              onClick={() => setLayout('individual')}
            >
              Individual
            </button>
          </div>
        </div>
      </div>

      <Card as="section" className="analytics-chart" ariaLabel="Offers by package band">
        <header className="analytics-chart__head">
          <div>
            <h2 className="analytics-chart__title">Offers by package band</h2>
            <p className="analytics-chart__sub">
              {count(totalOffers)} offers across {bands.length} fixed bands, split by CTC disclosure.
            </p>
          </div>
        </header>

        {layout === 'combined' ? (
          <LineChart
            categories={categories}
            series={combinedSeries}
            mode={mode}
            yUnit="offers"
            ariaLabel={`Offers by package band for batch ${data.batch}: ${combinedSeries
              .map((entry) => `${entry.label} peak ${Math.max(...entry.values.map((value) => value ?? 0))} offers`)
              .join('; ')}.`}
          />
        ) : (
          <div className="analytics-chart__multiples">
            {individualSeries.length === 0 ? (
              <p className="analytics-empty-note">
                Pick at least one branch above to draw its distribution alongside the all-branches line.
              </p>
            ) : (
              individualSeries.map(({ reference, own }) => (
                <div className="analytics-multiple" key={own.key}>
                  <h3 className="analytics-multiple__title">{own.label}</h3>
                  <LineChart
                    categories={categories}
                    series={[reference, own]}
                    mode={mode}
                    yUnit="offers"
                    ariaLabel={`Offers by package band for ${own.label}, batch ${data.batch}, compared with all branches.`}
                  />
                </div>
              ))
            )}
          </div>
        )}

        <ul className="analytics-legend">
          {legend.map((entry) => (
            <li className="analytics-legend__item" key={entry.key}>
              <span
                className="analytics-legend__swatch"
                aria-hidden="true"
                style={{
                  background: entry.stroke,
                  opacity: entry.dash ? 1 : 0.9,
                }}
              />
              {entry.label}
            </li>
          ))}
        </ul>
      </Card>

      {/* Four-cell strip of the same composition as the Analytics hero. Only
          "CTC disclosed" is an X / Y (194 of 382 offers); the other three are
          standalone figures with no denominator — see
          components/ui/StatCard/metricKind.ts. */}
      <MetricStrip
        ariaLabel="Distribution summary"
        items={[
          {
            key: 'offers',
            label: 'Offers counted',
            value: count(totalOffers),
            sublabel: 'across all fixed bands',
            tint: 'accent',
            icon: 'layers',
          },
          {
            key: 'disclosed',
            label: 'CTC disclosed',
            value: count(disclosedOffers),
            unit: `/ ${count(totalOffers)}`,
            sublabel: 'offers that named a figure',
            tint: 'teal',
            icon: 'info',
            progress: { current: disclosedOffers, total: totalOffers },
          },
          {
            key: 'band',
            label: 'Most common band',
            value: mostCommon ? shortBand(mostCommon.band) : '—',
            sublabel: mostCommon ? `${count(mostCommon.offers)} offers` : 'no disclosed offers yet',
            tint: 'indigo',
            icon: 'chart',
          },
          {
            key: 'ten-plus',
            label: '10 LPA and above',
            value: count(tenPlusOffers),
            sublabel:
              disclosedOffers > 0
                ? `${((tenPlusOffers / disclosedOffers) * 100).toFixed(1)}% of disclosed`
                : 'no disclosed offers yet',
            tint: 'violet',
            icon: 'award',
          },
        ]}
      />
    </div>
  );
}
