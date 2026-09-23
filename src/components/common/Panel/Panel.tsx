import { useId, type ReactNode } from 'react';
import { Icon, type IconName } from '../Icon/Icon';
import './Panel.scss';

interface PanelProps {
  icon: IconName;
  title: string;
  /** lg = main-column section (h2, roomier padding); sm = sidebar card (h3). */
  size?: 'lg' | 'sm';
  /** Right-aligned mono caption chip in the header (e.g. stage count). */
  meta?: ReactNode;
  /** Right-aligned count circle in the header (documents). */
  count?: number;
  id?: string;
  className?: string;
  children: ReactNode;
}

/**
 * Shared details-page section shell: bordered white card with an icon-tile
 * heading row (optional meta chip / count circle) over a divider — the one
 * place that defines panel chrome for description, requirements, flow,
 * metadata, documents and telemetry.
 */
export function Panel({ icon, title, size = 'lg', meta, count, id, className, children }: PanelProps) {
  const titleId = useId();
  const Heading = size === 'lg' ? 'h2' : 'h3';
  const classes = ['panel', `panel--${size}`, className].filter(Boolean).join(' ');

  return (
    <section className={classes} id={id} aria-labelledby={titleId}>
      <div className="panel__head">
        <div className="panel__head-main">
          <span className="panel__icon" aria-hidden="true">
            <Icon name={icon} size={18} />
          </span>
          <Heading id={titleId} className="panel__title">
            {title}
          </Heading>
        </div>
        {meta ? <span className="panel__meta">{meta}</span> : null}
        {count !== undefined ? <span className="panel__count">{count}</span> : null}
      </div>
      <div className="panel__body">{children}</div>
    </section>
  );
}
