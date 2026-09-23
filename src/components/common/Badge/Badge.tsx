import type { ReactNode } from 'react';
import './Badge.scss';

export type BadgeTone = 'success' | 'warning' | 'danger' | 'neutral' | 'info';

const STATUS_TONES: Record<string, BadgeTone> = {
  active: 'success',
  closed: 'neutral',
  expired: 'danger',
  draft: 'warning',
  inactive: 'neutral',
};

/** Tone derived from a backend status string — unknown values stay neutral. */
export function statusTone(status: string | null | undefined): BadgeTone {
  return STATUS_TONES[(status ?? '').toLowerCase()] ?? 'neutral';
}

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  /** Status dot before the label — pulses on success/active (live availability). */
  dot?: boolean;
  className?: string;
}

export function Badge({ children, tone = 'neutral', dot = false, className }: BadgeProps) {
  return (
    <span className={['badge', `badge--${tone}`, className].filter(Boolean).join(' ')}>
      {dot ? <span className="badge__dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}
