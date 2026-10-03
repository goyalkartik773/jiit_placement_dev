import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import type { IconBadgeTone } from '../../ui/IconBadge/IconBadge';
import { IconBadge } from '../../ui/IconBadge/IconBadge';
import type { EmailNotice } from '../../../types/dashboard.types';
import { deadlineInfo, formatRelative } from '../../../utils/format';
import './NoticeRow.scss';

/**
 * Per-category cue for the icon tile: a muted icon on a soft tint. Colour
 * follows the product's rules - accent marks the selection family, green the
 * events run for their own sake, amber the sign-ups, and everything else
 * stays neutral until it means something.
 */
interface ClassCue {
  icon: IconName;
  tone: IconBadgeTone;
}

const CLASSIFICATION_CUES: Record<string, ClassCue> = {
  SHORTLIST: { icon: 'users', tone: 'accent' },
  SELECTION_PROCESS_NOTICE: { icon: 'layers', tone: 'accent' },
  HACKATHON: { icon: 'zap', tone: 'green' },
  REGISTRATION: { icon: 'checklist', tone: 'amber' },
  WEBINAR: { icon: 'book', tone: 'neutral' },
  WORKSHOP: { icon: 'book', tone: 'neutral' },
  EVENT: { icon: 'flag', tone: 'neutral' },
  JOB_OPPORTUNITY: { icon: 'briefcase', tone: 'neutral' },
  INTERNSHIP_OPPORTUNITY: { icon: 'briefcase', tone: 'neutral' },
  GENERAL_PLACEMENT_NOTICE: { icon: 'info', tone: 'neutral' },
  UNKNOWN: { icon: 'tag', tone: 'neutral' },
};

const DEFAULT_CUE: ClassCue = { icon: 'tag', tone: 'neutral' };

/** "GENERAL_PLACEMENT_NOTICE" -> "General placement notice". */
export function classificationLabelOf(classification: string): string {
  const words = (classification || '').replace(/_/g, ' ').trim().toLowerCase();
  if (!words) return 'Unclassified';
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Shared by the row, the detail header and the rail, so all three agree. */
export function classificationCueOf(classification: string): ClassCue {
  return CLASSIFICATION_CUES[(classification || '').toUpperCase()] ?? DEFAULT_CUE;
}

/** Triage marks, all session-local - see the workspace header in EmailNotices. */
export interface NoticeMarks {
  starred: boolean;
  unread: boolean;
  archived: boolean;
}

interface NoticeRowProps {
  notice: EmailNotice;
  selected: boolean;
  marks: NoticeMarks;
  onSelect: (id: string) => void;
}

/**
 * One notice as a LIST ROW, not a card.
 *
 * Three lines and it is done: a meta line (classification, deadline, when it
 * landed), the subject as the thing you actually scan for, then the company
 * and one line of what it said. Everything the old card put in a pill - the
 * round counts, the shortlist size - belongs to the detail pane now, because
 * a list you are skimming cannot afford six badges per row.
 *
 * It is a `<button>`, so it is reachable by keyboard and announces itself as
 * one control; `aria-current` carries the selection rather than a div with a
 * click handler. The whole row is the target - there is no second, smaller
 * "read more" to hunt for, since opening it IS the point of a row.
 */
export function NoticeRow({ notice, selected, marks, onSelect }: NoticeRowProps) {
  const cue = classificationCueOf(notice.classification);
  const label = (notice.classificationlabel ?? '').trim() || classificationLabelOf(notice.classification);
  const deadline = deadlineInfo(notice.deadline);
  const when = formatRelative(notice.receivedat);
  const headline = (notice.headline ?? '').trim();
  const snippet = (notice.snippet ?? '').trim();
  const lead = headline || snippet;

  return (
    <li className="nrow-item">
      <button
        type="button"
        className="nrow"
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(notice.id)}
      >
        <IconBadge icon={cue.icon} tone={cue.tone} size={30} iconSize={15} />

        <span className="nrow__main">
          <span className="nrow__meta">
            <span className="nrow__class">{label}</span>
            {deadline ? (
              <span className={`nrow__deadline${deadline.urgent ? ' is-urgent' : ''}`}>
                <Icon name="calendar" size={11} />
                {deadline.text}
              </span>
            ) : null}
            <span className="nrow__when">{when ?? ''}</span>
          </span>

          <span className="nrow__subject">
            {marks.unread ? <span className="sr-only">Unread. </span> : null}
            {notice.subject}
          </span>

          <span className="nrow__line">
            {notice.company ? <span className="nrow__company">{notice.company}</span> : null}
            {lead ? <span className="nrow__snippet">{lead}</span> : null}
          </span>
        </span>

        <span className="nrow__flags" aria-hidden="true">
          {marks.starred ? <Icon name="star" size={13} className="nrow__flag nrow__flag--star" /> : null}
          {marks.archived ? <Icon name="archive" size={13} className="nrow__flag" /> : null}
          {notice.hasattachments ? <Icon name="paperclip" size={13} className="nrow__flag" /> : null}
          {notice.isrevision ? <span className="nrow__revised">R</span> : null}
        </span>
      </button>
    </li>
  );
}
