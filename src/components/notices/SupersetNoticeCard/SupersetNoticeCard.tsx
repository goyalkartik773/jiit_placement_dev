import { useId, useMemo, useState } from 'react';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Icon } from '../../common/Icon/Icon';
import { Prose } from '../../common/Prose/Prose';
import type { SupersetNotice } from '../../../types/dashboard.types';
import { formatDate, formatDateTime } from '../../../utils/format';
import { htmlToPlainText } from '../../../utils/html';
import './SupersetNoticeCard.scss';

interface SupersetNoticeCardProps {
  notice: SupersetNotice;
}

/**
 * One notice synced from the Superset job portal. The body is parsed into
 * blocks and rendered as text-only markup (`Prose`) - never as HTML - so a
 * bullet list comes out as real `<ul><li>` with a hanging indent.
 */
export function SupersetNoticeCard({ notice }: SupersetNoticeCardProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const body = useMemo(() => htmlToPlainText(notice.content), [notice.content]);
  const isRevised = Boolean(notice.updateddatetime && notice.updateddatetime !== notice.posteddatetime);

  return (
    <article className="superset-notice">
      <div className="superset-notice__top">
        <Badge tone={statusTone(notice.status)} dot={notice.status.toLowerCase() === 'active'}>
          {notice.status}
        </Badge>

        {notice.author ? (
          <span className="superset-notice__meta-item">
            <Icon name="users" size={14} />
            {notice.author}
          </span>
        ) : null}

        <span className="superset-notice__meta-item" title={formatDateTime(notice.posteddatetime)}>
          <Icon name="calendar" size={14} />
          Posted {formatDate(notice.posteddatetime)}
        </span>

        {isRevised ? (
          <span className="superset-notice__meta-item" title={formatDateTime(notice.updateddatetime)}>
            <Icon name="refresh" size={14} />
            Updated {formatDate(notice.updateddatetime)}
          </span>
        ) : null}
      </div>

      <h3 className="superset-notice__heading">
        <button
          type="button"
          className="superset-notice__toggle"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="superset-notice__title">{notice.title}</span>
          <span className="superset-notice__hint">{open ? 'Hide' : 'Read more'}</span>
          <span className="superset-notice__chevron" aria-hidden="true">
            <Icon name="chevron-down" size={16} />
          </span>
        </button>
      </h3>

      <div className="superset-notice__body" id={panelId} hidden={!open}>
        <Prose content={notice.content} className="superset-notice__content" />
        {!body ? <p className="superset-notice__content">This notice has no body text.</p> : null}
      </div>
    </article>
  );
}
