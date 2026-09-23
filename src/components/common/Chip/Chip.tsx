import type { ReactNode } from 'react';
import './Chip.scss';

interface ChipProps {
  children: ReactNode;
  title?: string;
  tone?: 'default' | 'accent' | 'muted';
}

/** Compact tag used for categories, criteria, skills and genders. */
export function Chip({ children, title, tone = 'default' }: ChipProps) {
  return (
    <span className={`chip chip--${tone}`} title={title}>
      {children}
    </span>
  );
}
