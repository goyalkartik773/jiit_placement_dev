import type { ReactNode } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import './StatTile.scss';

export type StatTileTone = 'neutral' | 'accent' | 'green' | 'amber';

interface StatTileProps {
  /** Short label above the number. */
  label: string;
  /** The number itself — already formatted by the caller. */
  value: ReactNode;
  /** Optional supporting line under the number (never a second number). */
  hint?: ReactNode;
  icon?: IconName;
  tone?: StatTileTone;
  className?: string;
}

/**
 * One hero statistic: a soft-tinted tile with a label, a large tabular number
 * and an optional quiet hint. Used by the client Dashboard's hero row.
 *
 * It renders whatever it is handed — it never derives, rounds or invents a
 * value, so every tile stays traceable to the feed it came from.
 */
export function StatTile({ label, value, hint, icon, tone = 'neutral', className = '' }: StatTileProps) {
  const classes = ['ui-stat-tile', `ui-stat-tile--${tone}`, className].filter(Boolean).join(' ');
  return (
    <div className={classes}>
      <div className="ui-stat-tile__head">
        <span className="ui-stat-tile__label">{label}</span>
        {icon ? <Icon name={icon} size={16} className="ui-stat-tile__icon" /> : null}
      </div>
      <p className="ui-stat-tile__value">{value}</p>
      {hint ? <p className="ui-stat-tile__hint">{hint}</p> : null}
    </div>
  );
}
