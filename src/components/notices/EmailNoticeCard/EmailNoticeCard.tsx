import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import { Avatar } from '../../ui/Avatar/Avatar';
import { IconBadge, type IconBadgeTone } from '../../ui/IconBadge/IconBadge';
import { Pill, type PillTone } from '../../ui/Pill/Pill';
import type { EmailNotice } from '../../../types/dashboard.types';
import { formatDate, formatDateTime } from '../../../utils/format';
import './EmailNoticeCard.scss';

/**
 * Per-category cue for the icon tile: a muted icon on a soft tint, replacing
 * the old plain text label. Colour follows the product's rules - accent marks
 * the selection family, green the events run for their own sake, amber the
 * sign-ups, and everything else stays neutral until it means something.
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

function cueFor(classification: string): ClassCue {
  return CLASSIFICATION_CUES[(classification || '').toUpperCase()] ?? DEFAULT_CUE;
}

/** How close a deadline is, in whole calendar days. */
function daysUntil(value: string): number | null {
  const raw = value.includes('T') ? value : `${value}T00:00:00`;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const that = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  return Math.round((that - today) / 86_400_000);
}

/**
 * Deadline wording + urgency. A date that has passed or lands inside a week is
 * urgent (red); further out it stays a quiet piece of metadata.
 * Date-only strings are parsed as local dates so they never shift a day.
 */
function deadlineInfo(value: string | null): { text: string; urgent: boolean } | null {
  if (!value) return null;
  const raw = value.includes('T') ? value : `${value}T00:00:00`;
  const days = daysUntil(value);
  if (days === null) return null;
  const label = formatDate(raw);
  if (days < 0) return { text: `Deadline passed ${label}`, urgent: true };
  if (days === 0) return { text: `Deadline today · ${label}`, urgent: true };
  if (days <= 7) return { text: `Deadline in ${days} day${days === 1 ? '' : 's'} · ${label}`, urgent: true };
  return { text: `Deadline ${label}`, urgent: false };
}

interface StatChip {
  key: string;
  text: string;
  tone: PillTone;
  icon?: IconName;
}

interface EmailNoticeCardProps {
  notice: EmailNotice;
}

/**
 * One parsed placement email.
 *
 * Order is fixed by the revamp: category icon tile + label, the subject as a
 * bold title, the company / one-line preview, then the footer with the sender
 * avatar and a muted timestamp. Counts are pills, deadlines sit in the top row
 * and turn red the moment they are close or gone.
 */
export function EmailNoticeCard({ notice }: EmailNoticeCardProps) {
  const label = (notice.classificationlabel ?? '').trim() || classificationLabelOf(notice.classification);
  const cue = cueFor(notice.classification);
  const deadline = deadlineInfo(notice.deadline);
  const studentCount = notice.studentcount;

  const stats: StatChip[] = [];
  const headline = (notice.headline ?? '').trim();
  if (headline) stats.push({ key: 'headline', text: headline, tone: 'neutral' });
  if (studentCount !== null && studentCount > 0) {
    stats.push({
      key: 'count',
      text: `${studentCount} student${studentCount === 1 ? '' : 's'} shortlisted`,
      tone: 'accent',
      icon: 'users',
    });
  }
  for (const round of notice.rounds ?? []) {
    stats.push({ key: `round-${round.round}`, text: `${round.round}: ${round.count}`, tone: 'neutral' });
  }

  return (
    <article className="email-notice">
      {/* ----- category tile + label, attachments, deadline ----- */}
      <div className="email-notice__top">
        <IconBadge icon={cue.icon} tone={cue.tone} size={34} iconSize={17} label={label} />
        <span className="email-notice__category">{label}</span>

        {notice.isrevision ? <span className="email-notice__tag">Revised</span> : null}

        {notice.hasattachments ? (
          <span className="email-notice__flag" title="This email has attachments">
            <Icon name="paperclip" size={14} />
            <span className="sr-only">Has attachments</span>
          </span>
        ) : null}

        {deadline ? (
          <span
            className={`email-notice__deadline${deadline.urgent ? ' is-urgent' : ''}`}
            title={`Deadline: ${notice.deadline}`}
          >
            <Icon name="calendar" size={14} />
            {deadline.text}
          </span>
        ) : null}
      </div>

      {/* ----- bold title ----- */}
      <h3 className="email-notice__subject">{notice.subject}</h3>

      {/* ----- company/source line + one-line preview ----- */}
      <p className="email-notice__source">
        <span className="email-notice__source-icon" aria-hidden="true">
          <Icon name={notice.company ? 'building' : 'briefcase'} size={15} />
        </span>
        {notice.company ? <span className="email-notice__company">{notice.company}</span> : null}
        {notice.snippet ? (
          <span className="email-notice__preview" title={notice.snippet}>
            {notice.snippet}
          </span>
        ) : null}
      </p>

      {/* ----- counts as pill-style stats ----- */}
      {stats.length > 0 ? (
        <ul className="email-notice__stats" aria-label="Figures reported in this email">
          {stats.map((stat) => (
            <li key={stat.key}>
              <Pill tone={stat.tone}>
                {stat.icon ? <Icon name={stat.icon} size={14} /> : null}
                {stat.text}
              </Pill>
            </li>
          ))}
        </ul>
      ) : null}

      {/* ----- footer: sender avatar + muted timestamp ----- */}
      <div className="email-notice__footer">
        <span className="email-notice__sender" title={`From ${notice.sender} <${notice.senderemail}>`}>
          <Avatar name={notice.sender || notice.senderemail} size={26} radius={8} />
          <span className="email-notice__sender-name">{notice.sender}</span>
          <span className="email-notice__sender-email">{notice.senderemail}</span>
        </span>

        <span className="email-notice__date">{formatDateTime(notice.receivedat)}</span>

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
