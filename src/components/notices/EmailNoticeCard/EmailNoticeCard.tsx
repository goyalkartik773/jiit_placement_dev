import { Badge, type BadgeTone } from '../../common/Badge/Badge';
import { Chip } from '../../common/Chip/Chip';
import { Icon } from '../../common/Icon/Icon';
import type { EmailNotice } from '../../../types/dashboard.types';
import { formatDate, formatDateTime } from '../../../utils/format';
import './EmailNoticeCard.scss';

/** Fixed colour coding per classification - unknown values stay neutral. */
const CLASSIFICATION_TONES: Record<string, BadgeTone> = {
  SHORTLIST: 'info',
  SELECTION_PROCESS_NOTICE: 'info',
  JOB_OPPORTUNITY: 'success',
  INTERNSHIP_OPPORTUNITY: 'success',
  REGISTRATION: 'warning',
  GENERAL_PLACEMENT_NOTICE: 'neutral',
  EVENT: 'neutral',
  WEBINAR: 'neutral',
  WORKSHOP: 'neutral',
  HACKATHON: 'neutral',
  UNKNOWN: 'neutral',
};

/** "GENERAL_PLACEMENT_NOTICE" -> "General placement notice". */
export function classificationLabelOf(classification: string): string {
  const words = (classification || '').replace(/_/g, ' ').trim().toLowerCase();
  if (!words) return 'Unclassified';
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Badge tone for a classification code. */
export function classificationTone(classification: string): BadgeTone {
  return CLASSIFICATION_TONES[(classification || '').toUpperCase()] ?? 'neutral';
}

/**
 * Date-only deadlines ("2026-09-28") are parsed as local dates so they never
 * shift a day in another timezone; full timestamps use the shared formatter.
 */
function formatDeadline(value: string): string {
  return value.includes('T') ? formatDate(value) : formatDate(`${value}T00:00:00`);
}

interface EmailNoticeCardProps {
  notice: EmailNotice;
}

/** One parsed placement email: classification, subject, funnel and metadata. */
export function EmailNoticeCard({ notice }: EmailNoticeCardProps) {
  const label = (notice.classificationlabel ?? '').trim() || classificationLabelOf(notice.classification);
  const studentCount = notice.studentcount;

  return (
    <article className="email-notice">
      <div className="email-notice__top">
        <Badge tone={classificationTone(notice.classification)}>{label}</Badge>

        {notice.isrevision ? <Badge tone="warning">Revised</Badge> : null}

        {notice.hasattachments ? (
          <span className="email-notice__flag" title="This email has attachments">
            <Icon name="paperclip" size={14} />
            <span className="sr-only">Has attachments</span>
          </span>
        ) : null}
      </div>

      <h3 className="email-notice__subject">{notice.subject}</h3>

      <div className="email-notice__meta">
        {notice.company ? (
          <span className="email-notice__meta-item" title={`Company: ${notice.company}`}>
            <Icon name="building" size={14} />
            {notice.company}
          </span>
        ) : null}

        {notice.headline ? <span className="email-notice__headline">{notice.headline}</span> : null}

        {notice.deadline ? (
          <span className="email-notice__meta-item email-notice__deadline">
            <Icon name="calendar" size={14} />
            Deadline {formatDeadline(notice.deadline)}
          </span>
        ) : null}
      </div>

      <p className="email-notice__snippet">{notice.snippet}</p>

      {studentCount !== null && studentCount > 0 ? (
        <p className="email-notice__count">
          <Icon name="users" size={14} />
          {studentCount} student{studentCount === 1 ? '' : 's'} shortlisted
        </p>
      ) : null}

      {notice.rounds && notice.rounds.length > 0 ? (
        <ul className="email-notice__rounds" aria-label="Selection funnel reported in this email">
          {notice.rounds.map((round) => (
            <li key={round.round}>
              <Chip tone="muted" title={`${round.round}: ${round.count}`}>
                {round.round}: {round.count}
              </Chip>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="email-notice__footer">
        <span className="email-notice__sender" title={`From ${notice.sender} <${notice.senderemail}>`}>
          <Icon name="inbox" size={14} />
          <span className="email-notice__sender-name">{notice.sender}</span>
          <span className="email-notice__sender-email">{notice.senderemail}</span>
        </span>

        <span className="email-notice__date">
          <Icon name="clock" size={14} />
          {formatDateTime(notice.receivedat)}
        </span>

        {notice.link ? (
          <a
            className="email-notice__link"
            href={notice.link}
            target="_blank"
            rel="noopener noreferrer"
            title={notice.link}
          >
            Open notice
            <Icon name="external-link" size={13} />
          </a>
        ) : null}
      </div>
    </article>
  );
}
