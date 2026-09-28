import { useId, useMemo, useState } from 'react';
import { Icon } from '../../common/Icon/Icon';
import { Prose } from '../../common/Prose/Prose';
import { Avatar } from '../../ui/Avatar/Avatar';
import type { SupersetNotice } from '../../../types/dashboard.types';
import { formatDate, formatDateTime, isTodayOrYesterday } from '../../../utils/format';
import { htmlToPlainText } from '../../../utils/html';
import './SupersetNoticeCard.scss';

interface SupersetNoticeCardProps {
  notice: SupersetNotice;
}

/**
 * One notice synced from the Superset job portal.
 *
 * Reading order: who posted it (initial avatar + author) and whether it is
 * still active, then the title as the big anchor, then one muted meta line
 * carrying `Posted ... · Updated ...`, and finally the body behind an inline
 * disclosure. The body is parsed into blocks and rendered by <Prose/> - never
 * as HTML - so a bullet list comes out as a real `<ul><li>` with a hanging
 * indent (Part 1).
 */
export function SupersetNoticeCard({ notice }: SupersetNoticeCardProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const body = useMemo(() => htmlToPlainText(notice.content), [notice.content]);
  const isRevised = Boolean(notice.updateddatetime && notice.updateddatetime !== notice.posteddatetime);
  const active = notice.status.toLowerCase() === 'active';
  // "Recently updated" only means *this* morning or last night - anything
  // older is already covered by the plain "Updated <date>" on the meta line.
  const fresh = isTodayOrYesterday(notice.updateddatetime);

  return (
    <article className="superset-notice">
      {/* ----- author + status ----- */}
      <header className="superset-notice__head">
        <Avatar name={notice.author || notice.title} size={34} radius={9} className="superset-notice__avatar" />
        <span className="superset-notice__author">{notice.author || 'Superset portal'}</span>

        <span
          className={`superset-notice__status${active ? ' superset-notice__status--active' : ''}`}
          title={`Notice status: ${notice.status}`}
        >
          <span className="superset-notice__dot" aria-hidden="true" />
          {notice.status}
        </span>

        {fresh ? (
          <span className="superset-notice__tag" aria-label="Updated today or yesterday">
            Recently updated
          </span>
        ) : null}
      </header>

      {/* ----- title: the anchor, doubles as the disclosure control ----- */}
      <h3 className="superset-notice__heading">
        <button
          type="button"
          className="superset-notice__toggle"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="superset-notice__title">{notice.title}</span>
          <span className="superset-notice__chevron" aria-hidden="true">
            <Icon name="chevron-down" size={17} />
          </span>
        </button>
      </h3>

      {/* ----- one muted meta line: Posted ... · Updated ... ----- */}
      <p className="superset-notice__meta">
        <span title={`Posted ${formatDateTime(notice.posteddatetime)}`}>
          Posted {formatDate(notice.posteddatetime)}
        </span>
        {isRevised ? (
          <>
            {' '}
            <span className="superset-notice__sep" aria-hidden="true">
              ·
            </span>{' '}
            <span title={`Updated ${formatDateTime(notice.updateddatetime)}`}>
              Updated {formatDate(notice.updateddatetime)}
            </span>
          </>
        ) : null}
        <span className="superset-notice__hint">{open ? 'Hide' : 'Read more'}</span>
      </p>

      <div className="superset-notice__body" id={panelId} hidden={!open}>
        <Prose content={notice.content} className="superset-notice__content" />
        {!body ? <p className="superset-notice__content">This notice has no body text.</p> : null}
      </div>
    </article>
  );
}
