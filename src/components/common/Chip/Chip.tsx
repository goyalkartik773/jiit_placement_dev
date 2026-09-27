import type { ReactNode } from 'react';
import './Chip.scss';

interface ChipProps {
  children: ReactNode;
  title?: string;
  tone?: 'default' | 'accent' | 'muted';
  /** Extra class for a variant (e.g. `chip--mono` for data chips). */
  className?: string;
}

/** Compact tag used for categories, criteria, skills and genders. */
export function Chip({ children, title, tone = 'default', className }: ChipProps) {
  const classes = ['chip', `chip--${tone}`, className].filter(Boolean).join(' ');
  return (
    <span className={classes} title={title}>
      {children}
    </span>
  );
}
