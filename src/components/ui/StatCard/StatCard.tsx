import type { ReactNode } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import { ProgressBar } from '../ProgressBar/ProgressBar';
import { metricKind } from './metricKind';
import './StatCard.scss';

export type { MetricKind, StatProgress } from './metricKind';

/**
 * The card tints. Each maps to exactly one `--ui-tint-<tint>-bg` (the soft
 * fill) and `--ui-tint-<tint>-ink` (rail, icon, progress fill) pair declared
 * in `styles/_ui.scss`. The tint identifies the metric — it is the card's
 * light background plus its rail, never a status signal.
 * `neutral` is the fallback for a card with no assigned identity.
 */
export type StatCardTone = 'neutral' | 'accent' | 'indigo' | 'violet' | 'teal' | 'green' | 'amber';

interface StatCardProps {
  /** Short label above the number. Sentence case; the CSS never uppercases it. */
  label: string;
  /**
   * The number alone, already formatted — "420", "11.67", "345". Keep the
   * unit out of it and pass it to `unit` instead: that is what stops
   * "11.67 LPA" from stacking onto two lines inside a narrow tile.
   */
  value: ReactNode;
  /** The small muted text that follows the number: "LPA", "/ 1,322". */
  unit?: ReactNode;
  /** Supporting line under the number (never a second number). */
  sublabel?: ReactNode;
  icon?: IconName;
  tint?: StatCardTone;
  /**
   * THE ONLY visual a card may carry, and only for "X out of Y" metrics.
   * Read `metricKind.ts` before setting it: pass it when the printed value
   * literally is a ratio from one feed, and leave it off for every
   * standalone figure. Omitted ⇒ no markup beyond label / value / sublabel /
   * icon is added, by construction.
   */
  progress?: { current: number; total: number };
  /**
   * Marks a card whose figure is still in flight. The value shows an em dash
   * meanwhile, so assistive tech is told the number is pending rather than
   * being read a bare dash as if it were the answer.
   */
  ariaBusy?: boolean;
  /**
   * How the tile is framed — this is the only thing that differs between the
   * Dashboard and the Analytics hero, so both pages still share ONE component,
   * ONE decision rule and ONE type scale.
   *
   *  'card'  — standalone tile: own border, own shadow, 3px rail on the TOP
   *            edge. Used by the Dashboard hero and the tab-panel summaries.
   *  'strip' — a cell of `MetricStrip`: the panel owns the frame and the
   *            shadow, so the tile drops them and marks its column with a
   *            3px rail on the LEFT edge instead.
   */
  variant?: 'card' | 'strip';
  className?: string;
}

/**
 * One KPI tile: a soft tinted fill, a 3px tint rail, a neutral number.
 *
 * The fill is the light `--ui-tint-<tint>-bg` wash — enough colour for the six
 * metrics to be told apart at a glance, light enough that the number can stay
 * `--ui-ink` on every tile. So the six read as one system (same surface, same
 * border, same shadow, same type) rather than six different widgets, and the
 * label/sublabel use `--ui-tint-label`, the ink that was measured against
 * these washes (4.84–5.06:1) where the stock `--ui-muted` would drop to 4.3.
 *
 * It prints what it is handed: it never derives, rounds or invents a value,
 * so every tile stays traceable to the feed it came from.
 */
export function StatCard({
  label,
  value,
  unit,
  sublabel,
  icon,
  tint = 'neutral',
  progress,
  ariaBusy,
  variant = 'card',
  className = '',
}: StatCardProps) {
  const classes = [
    'ui-stat-card',
    `ui-stat-card--${tint}`,
    variant === 'strip' ? 'ui-stat-card--strip' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} data-metric-kind={metricKind(progress)} aria-busy={ariaBusy ? 'true' : undefined}>
      <div className="ui-stat-card__head">
        <span className="ui-stat-card__label">{label}</span>
        {icon ? <Icon name={icon} size={16} className="ui-stat-card__icon" /> : null}
      </div>

      <p className="ui-stat-card__value">
        <span className="ui-stat-card__figure">{value}</span>
        {unit ? <span className="ui-stat-card__unit">{unit}</span> : null}
      </p>

      {sublabel ? <p className="ui-stat-card__sublabel">{sublabel}</p> : null}

      {progress ? (
        <ProgressBar current={progress.current} total={progress.total} className="ui-stat-card__progress" />
      ) : null}
    </div>
  );
}
