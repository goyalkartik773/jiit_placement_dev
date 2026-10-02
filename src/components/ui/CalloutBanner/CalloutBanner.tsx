import type { ReactNode } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { IconBadge } from '../IconBadge/IconBadge';
import './CalloutBanner.scss';

/** The four tones with a real `--ui-tint-*` pair — red has none in this palette. */
export type CalloutTone = 'neutral' | 'accent' | 'green' | 'amber';

interface CalloutBannerProps {
  /**
   * The mark on the left. Always decorative: `eyebrow` and `title` are
   * required text, so the badge is never the sole cue for the meaning and
   * never has to announce itself.
   */
  icon: IconName;
  /** Small uppercase line above the statement ("RECORD OFFER"). */
  eyebrow: ReactNode;
  /** The statement itself — a company name, a sentence, a claim. */
  title: ReactNode;
  /** The figure, already formatted. Rendered at display scale on the right. */
  figure?: ReactNode;
  /** "LPA", "students" — printed as its own span so the figure never wraps. */
  unit?: ReactNode;
  tone?: CalloutTone;
  className?: string;
}

/**
 * One full-width strip that says a single thing: an eyebrow, a statement, an
 * optional figure.
 *
 * WHY IT EXISTS. A record ("the highest package this season is 56 LPA from
 * Zomato") is not a StatCard — it has no denominator, no sublabel, no X/Y —
 * and it is not a hero either; there is only one of it and it is not the
 * page's anchor. Squeezing it into either shape made the page read as either
 * a wall of tiles or a headline with an afterthought. This is the third
 * shape: the same tinted surface family as the tiles, at full width, with the
 * figure promoted to the right edge where the eye lands last and remembers.
 *
 * It prints what it is handed: nothing here is derived, rounded or invented,
 * so the banner stays traceable to the row it came from.
 *
 * COLOURS — tokens only: the `--ui-tint-<tone>-bg` wash and `-ink` for the
 * rail, border, eyebrow and icon; `--ui-ink` for the statement and figure.
 * Every pairing clears 4.5:1 on its own wash.
 */
export function CalloutBanner({
  icon,
  eyebrow,
  title,
  figure,
  unit,
  tone = 'amber',
  className = '',
}: CalloutBannerProps) {
  const classes = ['ui-callout', `ui-callout--${tone}`, className].filter(Boolean).join(' ');

  return (
    <section className={classes}>
      <IconBadge icon={icon} tone={tone} size={42} iconSize={20} className="ui-callout__badge" />

      <div className="ui-callout__body">
        <p className="ui-callout__eyebrow">{eyebrow}</p>
        <p className="ui-callout__title">{title}</p>
      </div>

      {figure !== undefined ? (
        <p className="ui-callout__figure">
          <span className="ui-callout__value">{figure}</span>
          {unit ? <span className="ui-callout__unit">{unit}</span> : null}
        </p>
      ) : null}
    </section>
  );
}
