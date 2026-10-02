import type { ReactNode } from 'react';
import './PageHeader.scss';

/**
 * One eyebrow string for every placement screen. The casing is applied by the
 * component, so pages stop disagreeing on dash style and capitalisation.
 */
export const SESSION_EYEBROW = 'Placement Cell · Session 2026–27';

interface PageHeaderProps {
  /** Small uppercase label above the title. Use `SESSION_EYEBROW` unless the
   *  screen genuinely measures something else. */
  eyebrow: ReactNode;
  /** The page's single `<h1>`. */
  title: string;
  /**
   * The standing summary sentence — the line that answers "what does this
   * screen say". Wrap the figures in a plain `<strong>`: the component
   * prints those at a fixed lead scale, so both pages get identical
   * emphasis without a bespoke class per page.
   */
  summary?: ReactNode;
  /**
   * The summary's framing — the second axis the two pages differ on:
   *
   *  'card'  — the bordered accent card (Dashboard). Reads as the page's
   *            thesis, where inline muted text read as a caption.
   *  'report' — a plain inline meta line closed by a hairline rule under the
   *            whole header. No box, no left bar: Analytics opens like a
   *            report sheet, the Dashboard like a homepage.
   */
  variant?: 'card' | 'report';
  className?: string;
}

/**
 * The top block shared by every page that opens with eyebrow · title ·
 * summary. One component, one stylesheet, so the Dashboard and Analytics are
 * built from the same block instead of being two near-duplicates that drift
 * apart — they differ only by the `variant` they ask for.
 */
export function PageHeader({ eyebrow, title, summary, variant = 'card', className = '' }: PageHeaderProps) {
  const classes = ['page-header', variant === 'report' ? 'page-header--report' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <header className={classes}>
      <p className="page-header__eyebrow">{eyebrow}</p>
      <h1 className="page-header__title">{title}</h1>
      {summary ? (
        <p
          className={
            variant === 'report' ? 'page-header__summary page-header__summary--line' : 'page-header__summary'
          }
        >
          {summary}
        </p>
      ) : null}
    </header>
  );
}
