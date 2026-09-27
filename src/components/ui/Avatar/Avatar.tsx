import { initials } from '../../../utils/format';
import './Avatar.scss';

/** Soft tints used purely to tell company marks apart — never saturated. */
const TINTS = 5;

interface AvatarProps {
  /** Company name — the initials are derived from it, never stored. */
  name: string | null | undefined;
  /** Edge length in px (44 on both screens). */
  size?: number;
  /** Corner radius in px — 11 on job cards, 12 on company rows. */
  radius?: number;
  className?: string;
}

function tintIndex(name: string | null | undefined): number {
  const value = name ?? '';
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  return hash % TINTS;
}

/**
 * Soft-tinted rounded square holding a company's initials. Shared by the Active
 * Job Listing cards and the Company-Wise Placement rows so both screens read as
 * the same product; the tint rotates deterministically per company name.
 */
export function Avatar({ name, size = 44, radius = 11, className = '' }: AvatarProps) {
  const classes = ['ui-avatar', `ui-avatar--t${tintIndex(name)}`, className].filter(Boolean).join(' ');
  const style = { width: `${size}px`, height: `${size}px`, borderRadius: `${radius}px` };
  return (
    <span className={classes} style={style} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
