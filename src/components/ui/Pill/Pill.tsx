import type { ReactNode } from 'react';
import './Pill.scss';

export type PillTone = 'neutral' | 'accent' | 'green' | 'red';

interface PillProps {
  children: ReactNode;
  /** Neutral is the default; colour only where the meaning is real. */
  tone?: PillTone;
  className?: string;
  /** Full text when the pill has to ellipsis on a narrow card. */
  title?: string;
}

/**
 * The single pill/badge of the calm design system. Neutral gray carries every
 * tag, chip and selected filter that means nothing in particular; accent marks
 * a primary/eligible selection, green money and positive counts, red passed
 * deadlines and urgent-only warnings.
 */
export function Pill({ children, tone = 'neutral', className = '', title }: PillProps) {
  return (
    <span className={['ui-pill', `ui-pill--${tone}`, className].filter(Boolean).join(' ')} title={title}>
      {children}
    </span>
  );
}
