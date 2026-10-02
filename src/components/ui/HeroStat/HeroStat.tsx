import type { ReactNode } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import { ProgressBar } from '../ProgressBar/ProgressBar';
import type { StatCardTone } from '../StatCard/StatCard';
import { metricKind } from '../StatCard/metricKind';
import './HeroStat.scss';

/**
 * One figure inside the hero. Deliberately the SAME field set as `StatCard` —
 * label / value / unit / sublabel / icon / progress — because a hero is a
 * StatCard at display scale, not a second vocabulary. `progress` obeys the
 * identical rule: a true X / Y from one feed, and nothing else.
 */
export interface HeroFigure {
  label: string;
  /** The number alone, already formatted. Keep the unit out of it. */
  value: ReactNode;
  /** "LPA", "/ 1,322" — printed as its own span so the figure cannot wrap. */
  unit?: ReactNode;
  sublabel?: ReactNode;
  icon?: IconName;
  progress?: { current: number; total: number };
}

interface HeroStatProps {
  /** THE anchor of the screen — the number the eye should land on first. */
  lead: HeroFigure;
  /**
   * The one figure worth standing beside it, split off by a hairline. Omit it
   * and the hero is a single full-width statement.
   */
  support?: HeroFigure;
  /** Tint identity for the `card` framing — same seven as `StatCard`. */
  tint?: StatCardTone;
  /**
   * The same two framings `PageHeader` offers, so the top of each screen is
   * consistent with itself:
   *
   *  'card'   — Dashboard: the tint wash, a 4px rail, the number in `--ui-ink`.
   *  'report' — Analytics: a white surface and a hairline frame, identity from
   *             `--ui-accent` instead of a wash. No rail.
   */
  variant?: 'card' | 'report';
  className?: string;
}

function FigureZone({ figure, size }: { figure: HeroFigure; size: 'lead' | 'support' }) {
  return (
    <div className={`ui-hero__zone ui-hero__zone--${size}`} data-metric-kind={metricKind(figure.progress)}>
      <p className="ui-hero__label">
        <span className="ui-hero__label-text">{figure.label}</span>
        {figure.icon ? <Icon name={figure.icon} size={size === 'lead' ? 20 : 16} className="ui-hero__icon" /> : null}
      </p>

      <p className="ui-hero__value">
        <span className="ui-hero__figure">{figure.value}</span>
        {figure.unit ? <span className="ui-hero__unit">{figure.unit}</span> : null}
      </p>

      {figure.sublabel ? <p className="ui-hero__sub">{figure.sublabel}</p> : null}

      {figure.progress ? (
        <ProgressBar current={figure.progress.current} total={figure.progress.total} className="ui-hero__bar" />
      ) : null}
    </div>
  );
}

/**
 * The screen's anchor.
 *
 * WHY THIS EXISTS. Six KPI tiles of equal weight give the eye nowhere to land:
 * everything is the same size, so nothing reads as the point. Promoting one
 * figure to display scale (44–58px against the tiles' 28px) and standing one
 * supporting ratio beside it is the single change that turns a row of boxes
 * into a headline — and it reuses the StatCard vocabulary rather than
 * inventing a parallel one, so the page is still one system.
 *
 * It prints what it is handed: nothing here derives, rounds or invents a
 * figure, and the only visual a zone may carry is the shared ProgressBar on
 * a true X / Y (`../StatCard/metricKind.ts`).
 *
 * COLOURS — tokens only: the `--ui-tint-*` pair from `styles/_ui.scss` for
 * the `card` wash, `--ui-panel` / `--ui-border` / `--ui-border-soft` /
 * `--ui-accent` for the `report` frame, `--ui-ink` for both figures and
 * `--ui-tint-label` for label and sublabel (4.84–5.06:1 on these washes).
 */
export function HeroStat({ lead, support, tint = 'accent', variant = 'card', className = '' }: HeroStatProps) {
  const classes = ['ui-hero', `ui-hero--${tint}`, `ui-hero--${variant}`, className].filter(Boolean).join(' ');

  return (
    <section className={classes} aria-label={lead.label}>
      <FigureZone figure={lead} size="lead" />
      {support ? <FigureZone figure={support} size="support" /> : null}
    </section>
  );
}
