import type { ReactNode } from 'react';
import { Icon, type IconName } from '../../common/Icon/Icon';
import type { TierKey } from '../../../utils/tiers';
import './MetricCard.scss';

export type MetricTone = TierKey | 'rose' | 'emerald' | 'amber' | 'ink' | 'secondary';

export interface MetricBadge {
  text: string;
  tone: MetricTone | 'mono';
}

interface MetricCardProps {
  icon: IconName;
  label: string;
  iconTone?: MetricTone;
  badge?: MetricBadge;
  footer?: { label: string; value: ReactNode };
  accent?: 'default' | 'blue' | 'rose';
  className?: string;
  /** Figure block — the value line plus an optional sub line. */
  children: ReactNode;
}

/**
 * One bento tile of the details metrics row (package / deadline / pool /
 * eligibility). Content is passed in as children so each call site owns the
 * data mapping; this component owns only the tile chrome.
 */
export function MetricCard({
  icon,
  label,
  iconTone = 'secondary',
  badge,
  footer,
  accent = 'default',
  className,
  children,
}: MetricCardProps) {
  const classes = ['metric-card', `metric-card--${accent}`, className].filter(Boolean).join(' ');

  return (
    <article className={classes}>
      <div className="metric-card__head">
        <span className="metric-card__label">
          <Icon name={icon} size={16} className={`metric-card__icon metric-card__icon--${iconTone}`} />
          {label}
        </span>
        {badge ? <span className={`metric-card__badge metric-card__badge--${badge.tone}`}>{badge.text}</span> : null}
      </div>

      <div className="metric-card__figure">{children}</div>

      {footer ? (
        <div className="metric-card__footer">
          <span className="metric-card__footer-label">{footer.label}</span>
          <span className="metric-card__footer-value">{footer.value}</span>
        </div>
      ) : null}
    </article>
  );
}
