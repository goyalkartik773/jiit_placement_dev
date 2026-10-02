import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import { Button } from '../../common/Button/Button';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import { Avatar } from '../../ui/Avatar/Avatar';
import { IconBadge, type IconBadgeTone } from '../../ui/IconBadge/IconBadge';
import { Pill, type PillTone } from '../../ui/Pill/Pill';
import { isAbortError } from '../../../services/apiClient';
import { fetchEmailNoticeDetail } from '../../../services/noticeService';
import type {
  EmailNotice,
  EmailNoticeDetail as EmailNoticeDetailData,
} from '../../../types/dashboard.types';
import { deadlineInfo, formatDateTime } from '../../../utils/format';
import { EmailNoticeDetail } from '../EmailNoticeDetail/EmailNoticeDetail';
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

interface StatChip {
  key: string;
  text: string;
  tone: PillTone;
  icon?: IconName;
}

interface EmailNoticeCardProps {
  notice: EmailNotice;
}

/** Detail fetch lifecycle: idle until the first "Read more" click. */
type DetailStatus = 'idle' | 'loading' | 'ready' | 'error';

/**
 * One parsed placement email.
 *
 * Order is fixed by the revamp: category icon tile + label, the subject as a
 * bold title, the company / one-line preview, then the footer with the sender
 * avatar, a muted timestamp and the "Read more" control. That button is the
 * disclosure — it carries `aria-expanded` and says what pressing it does,
 * where a title-turned-toggle only announced itself through a hover state.
 * The detail payload (full body, students, funnel evidence, attachments) is
 * fetched lazily on the FIRST expand and kept, so Hide/Show never re-hits
 * the API.
 */
export function EmailNoticeCard({ notice }: EmailNoticeCardProps) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<DetailStatus>('idle');
  const [detail, setDetail] = useState<EmailNoticeDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const panelId = useId();

  // Abort an in-flight fetch when the card unmounts (page/search change).
  useEffect(() => () => abortRef.current?.abort(), []);

  const loadDetail = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('loading');
    setError(null);
    try {
      const data = await fetchEmailNoticeDetail(notice.id, controller.signal);
      setDetail(data);
      setStatus('ready');
    } catch (err) {
      if (isAbortError(err)) return;
      setError(err instanceof Error ? err.message : 'Could not load this email.');
      setStatus('error');
    }
  }, [notice.id]);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next && status === 'idle') void loadDetail();
  };

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

      {/* ----- bold title. Content, not a control: the disclosure lives in
              the footer, where "Read more" says what pressing it does. ----- */}
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

      {/* ----- footer: sender avatar + muted timestamp + read-more hint ----- */}
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

        {/* This button owns the disclosure: it carries `aria-expanded` and
            `aria-controls`, so the control states plainly what it does. */}
        <button
          type="button"
          className={`email-notice__hint${open ? ' is-open' : ''}`}
          aria-expanded={open}
          aria-controls={panelId}
          onClick={handleToggle}
        >
          {open ? 'Hide' : 'Read more'}
          <Icon name="chevron-down" size={14} className="email-notice__hint-icon" />
        </button>
      </div>

      {/* ----- expanded detail: fetched once, then cached in state ----- */}
      <div className="email-notice__panel" id={panelId} hidden={!open}>
        {status === 'loading' ? (
          <div className="email-notice__loading" role="status">
            <span className="sr-only">Loading email details...</span>
            <Skeleton width="sm" height="xs" shape="pill" />
            <Skeleton width="full" height="lg" shape="rect" />
            <Skeleton width="full" height="lg" shape="rect" />
            <Skeleton width="full" height="md" shape="rect" />
          </div>
        ) : null}

        {status === 'error' ? (
          <p className="email-notice__error" role="alert">
            <Icon name="alert-circle" size={15} />
            <span>{error ?? 'Could not load this email.'}</span>
            <Button variant="soft" size="sm" icon="refresh" onClick={() => void loadDetail()}>
              Retry
            </Button>
          </p>
        ) : null}

        {status === 'ready' && detail ? <EmailNoticeDetail detail={detail} /> : null}
      </div>
    </article>
  );
}
