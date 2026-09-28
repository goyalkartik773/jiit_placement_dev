import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import './IconBadge.scss';

export type IconBadgeTone = 'neutral' | 'accent' | 'green' | 'amber' | 'red';

interface IconBadgeProps {
  icon: IconName;
  /**
   * Soft tint behind the icon. Colour carries meaning only where the meaning
   * is real (accent = the primary/selection family, green = success,
   * amber = attention, red = urgent, neutral = everything else).
   */
  tone?: IconBadgeTone;
  /** Edge length in px — the box is never smaller than the icon it holds. */
  size?: number;
  /** Icon size in px; defaults to a comfortable inset inside `size`. */
  iconSize?: number;
  className?: string;
  /** Accessible label when the badge is the only visible cue. */
  label?: string;
}

/**
 * Soft-tinted rounded square holding one icon. The tile is always at least
 * `size` px wide/tall and the icon keeps `flex-shrink: 0`, so neither can clip
 * the other — the failure mode this component exists to rule out.
 */
export function IconBadge({
  icon,
  tone = 'neutral',
  size = 36,
  iconSize = 18,
  className = '',
  label,
}: IconBadgeProps) {
  const classes = ['ui-icon-badge', `ui-icon-badge--${tone}`, className].filter(Boolean).join(' ');
  return (
    <span
      className={classes}
      style={{ width: `${size}px`, height: `${size}px` }}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <Icon name={icon} size={iconSize} />
    </span>
  );
}
