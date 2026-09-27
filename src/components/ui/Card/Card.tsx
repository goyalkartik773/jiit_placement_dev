import type { ReactNode } from 'react';
import './Card.scss';

type CardElement = 'div' | 'article' | 'section' | 'aside' | 'li';

interface CardProps {
  children: ReactNode;
  /** Semantic element — a job is an article, a summary strip a section. */
  as?: CardElement;
  /** Extra classes from the caller (layout, page-specific tuning). */
  className?: string;
  /** Accessible name when the card has no visible heading. */
  ariaLabel?: string;
}

/**
 * Shared card surface of the calm design system: white panel, 1px border,
 * 16px radius. It owns the surface only — padding and layout stay with the
 * caller so one component can serve a job card, a company card and a
 * full-width summary strip alike.
 */
export function Card({ children, as: Tag = 'div', className = '', ariaLabel }: CardProps) {
  const classes = ['ui-card', className].filter(Boolean).join(' ');
  return (
    <Tag className={classes} aria-label={ariaLabel}>
      {children}
    </Tag>
  );
}
