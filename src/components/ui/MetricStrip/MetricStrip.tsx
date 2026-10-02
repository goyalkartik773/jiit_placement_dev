import type { ReactNode } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { StatCard, type StatCardTone } from '../StatCard/StatCard';
import type { StatProgress } from '../StatCard/metricKind';
import './MetricStrip.scss';

/** One cell of the strip — the same fields as `StatCard`, nothing extra. */
export interface MetricStripItem {
  key: string;
  label: string;
  value: ReactNode;
  unit?: ReactNode;
  sublabel?: ReactNode;
  icon?: IconName;
  tint?: StatCardTone;
  progress?: StatProgress;
  /** Still-loading figure: prints an em dash and flags the cell `aria-busy`. */
  ariaBusy?: boolean;
}

interface MetricStripProps {
  items: MetricStripItem[];
  ariaLabel: string;
  className?: string;
}

/**
 * Analytics' hero metrics: ONE panel holding every figure, cells divided by
 * 1px hairlines — the report-strip composition (Stripe, Mixpanel, Metabase).
 *
 * This is the deliberate difference from the Dashboard, which presents the
 * same six numbers as six separate tiles on the open page. Same component
 * underneath (`StatCard`, `variant="strip"`), same tokens, same type scale,
 * same `metricKind` decision rule — only the framing changes, so the two
 * screens read as siblings from one system rather than as copies.
 *
 * The panel is deliberately NOT a list: cells are data, not repeating records,
 * and the 1px gaps are what draw the dividers (see MetricStrip.scss) so they
 * stay correct at every column count without a nth-child border to maintain.
 */
export function MetricStrip({ items, ariaLabel, className = '' }: MetricStripProps) {
  const classes = ['ui-metric-strip', className].filter(Boolean).join(' ');

  return (
    <section className={classes} aria-label={ariaLabel} data-cells={items.length}>
      {items.map((item) => (
        <StatCard
          key={item.key}
          variant="strip"
          label={item.label}
          value={item.value}
          unit={item.unit}
          sublabel={item.sublabel}
          icon={item.icon}
          tint={item.tint}
          progress={item.progress}
          ariaBusy={item.ariaBusy}
        />
      ))}
    </section>
  );
}
