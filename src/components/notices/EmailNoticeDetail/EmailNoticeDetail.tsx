import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { Icon } from '../../common/Icon/Icon';
import { Avatar } from '../../ui/Avatar/Avatar';
import { Prose } from '../../common/Prose/Prose';
import { SearchField } from '../../common/SearchField/SearchField';
import { Button } from '../../common/Button/Button';
import { Pill, type PillTone } from '../../ui/Pill/Pill';
import type {
  EmailNoticeDetail,
  NoticeRoundDetail,
  NoticeStudent,
} from '../../../types/dashboard.types';
import type { NoticeMarks } from '../NoticeRow/NoticeRow';
import { classificationLabelOf } from '../NoticeRow/NoticeRow';
import {
  deadlineInfo,
  fileIconKind,
  formatBytes,
  formatDate,
  formatDateTime,
  fileTypeLabel,
} from '../../../utils/format';
import { stripEmphasis } from '../../../utils/highlight';
import './EmailNoticeDetail.scss';

// --------------------------------------------------------------------------- #
// Small text helpers
// --------------------------------------------------------------------------- #

/** "llm" -> "LLM", "rule_based" -> "Rule based". */
function methodLabel(method: string | null): string | null {
  if (!method) return null;
  if (method.toLowerCase() === 'llm') return 'LLM';
  return method.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

/** Classifier confidence is 0..1; show it as a rounded percentage. */
function confidenceLabel(confidence: number | null, method: string | null): string | null {
  const parts: string[] = [];
  if (confidence !== null && confidence !== undefined && Number.isFinite(confidence)) {
    const pct = confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence);
    parts.push(`${pct}% match`);
  }
  const methodText = methodLabel(method);
  if (methodText) parts.push(methodText);
  return parts.length > 0 ? parts.join(' · ') : null;
}

/** "volunteered" -> "Volunteered", "online test" -> "Online test". */
function humanizeRound(name: string): string {
  const words = (name ?? '').replace(/_/g, ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : 'Round';
}

// --------------------------------------------------------------------------- #
// Action bar
// --------------------------------------------------------------------------- #

interface ActionBarProps {
  detail: EmailNoticeDetail;
  marks: NoticeMarks;
  onBack: () => void;
  onToggleStar: () => void;
  onToggleArchive: () => void;
  onToggleUnread: () => void;
}

/**
 * Back / Archive / Mark unread / Star / More, as icons.
 *
 * The bar is sticky inside the reading pane so it never scrolls out of reach
 * — a pane that is its own scroll context is exactly why it has to be. Back
 * is the only control with a label: it is the one whose icon alone is
 * ambiguous at this size, and at narrow widths it is the only way out of the
 * detail, so it earns the word.
 *
 * Triage does nothing behind the user's back: Archiving removes the notice
 * from the default list, and the list header carries an "Archived (n)" chip
 * with a one-click restore from the moment anything lands there.
 */
function ActionBar({ detail, marks, onBack, onToggleStar, onToggleArchive, onToggleUnread }: ActionBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape, the two ways a popover is expected to
  // dismiss itself. Registered only while open, so there is no listener cost
  // for the common case.
  useEffect(() => {
    if (!menuOpen) return;
    const onPointer = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setMenuOpen(false);
    } catch {
      // Clipboard permissions vary by browser; failing silently is better
      // than claiming a copy that did not happen.
      setMenuOpen(false);
    }
  };

  return (
    <div className="nd__bar">
      <button type="button" className="nd__back" onClick={onBack}>
        <Icon name="arrow-left" size={16} />
        <span>Back</span>
      </button>

      <div className="nd__actions">
        <button
          type="button"
          className="nd__icon-btn"
          aria-pressed={marks.archived}
          title={marks.archived ? 'Restore from archive' : 'Archive this notice'}
          onClick={onToggleArchive}
        >
          <Icon name="archive" size={17} />
          <span className="sr-only">{marks.archived ? 'Restore from archive' : 'Archive'}</span>
        </button>

        <button
          type="button"
          className="nd__icon-btn"
          aria-pressed={marks.unread}
          title={marks.unread ? 'Mark as read' : 'Mark as unread'}
          onClick={onToggleUnread}
        >
          <Icon name="mail" size={17} />
          <span className="sr-only">{marks.unread ? 'Mark as read' : 'Mark as unread'}</span>
        </button>

        <button
          type="button"
          className={`nd__icon-btn${marks.starred ? ' is-on' : ''}`}
          aria-pressed={marks.starred}
          title={marks.starred ? 'Remove star' : 'Star this notice'}
          onClick={onToggleStar}
        >
          <Icon name="star" size={17} />
          <span className="sr-only">{marks.starred ? 'Remove star' : 'Star'}</span>
        </button>

        <div className="nd__more" ref={menuRef}>
          <button
            type="button"
            className={`nd__icon-btn${menuOpen ? ' is-on' : ''}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            title="More actions"
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Icon name="more-horizontal" size={17} />
            <span className="sr-only">More actions</span>
          </button>

          {menuOpen ? (
            <div className="nd__menu" role="menu">
              <button type="button" role="menuitem" className="nd__menu-item" onClick={() => void copyLink()}>
                <Icon name="file" size={15} />
                {copied ? 'Link copied' : 'Copy link to this notice'}
              </button>
              {detail.link ? (
                <a
                  role="menuitem"
                  className="nd__menu-item"
                  href={detail.link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Icon name="external-link" size={15} />
                  Open registration link
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- #
// Compact header — this replaces the old "Key details" grid of cards
// --------------------------------------------------------------------------- #

function Chip({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <span className="nd__chip" title={title}>
      {children}
    </span>
  );
}

/**
 * The whole header is one block of text, not a grid of boxed facts: a
 * classification line, the subject, then who it came from and when.
 *
 * Everything the old grid carried is still here — sender, recipient, cc,
 * received, type, confidence, company, headline, deadline — it is just
 * expressed as an address block instead of eight bordered tiles, which is
 * how a reader recognises an email in the first place.
 */
function HeaderSection({ detail }: { detail: EmailNoticeDetail }) {
  const conf = confidenceLabel(detail.confidence, detail.method);
  const deadline = deadlineInfo(detail.deadline);
  const label = (detail.classificationlabel ?? '').trim() || classificationLabelOf(detail.classification);
  const interviewDates = Array.isArray(detail.interviewdates) ? detail.interviewdates : [];
  const stages = detail.stages ?? [];
  const eligibility = detail.eligibility ?? [];
  const hasChips = interviewDates.length > 0 || stages.length > 0 || eligibility.length > 0;

  return (
    <header className="nd__head">
      <div className="nd__eyebrow">
        <span className="nd__class">{label}</span>
        {conf ? <span className="nd__conf">{conf}</span> : null}
        {detail.company ? <span className="nd__company">{detail.company}</span> : null}
        {deadline ? (
          <span className={`nd__deadline${deadline.urgent ? ' is-urgent' : ''}`} title={detail.deadline ?? undefined}>
            <Icon name="calendar" size={12} />
            {deadline.text}
          </span>
        ) : null}
      </div>

      <h2 className="nd__subject">{detail.subject}</h2>

      <div className="nd__address">
        <Avatar name={detail.sender || detail.senderemail} size={34} radius={9} />
        <span className="nd__who">
          <span className="nd__sender">{detail.sender || detail.senderemail}</span>
          {detail.senderemail && detail.senderemail !== detail.sender ? (
            <span className="nd__email">{detail.senderemail}</span>
          ) : null}
          <span className="nd__to">
            {detail.recipient ? `to ${detail.recipient}` : null}
            {detail.cc ? ` · cc ${detail.cc}` : null}
          </span>
        </span>
        <time className="nd__when" dateTime={detail.receivedat ?? undefined}>
          {formatDateTime(detail.receivedat)}
        </time>
      </div>

      {detail.headline ? (
        <p className="nd__headline" title={detail.stageraw && detail.stageraw !== detail.headline ? `As worded in the email: ${detail.stageraw}` : undefined}>
          {detail.headline}
        </p>
      ) : null}

      {hasChips ? (
        <div className="nd__chips">
          {interviewDates.map((value, index) => (
            <Chip key={`iv-${index}`} title={value}>
              <Icon name="calendar" size={13} />
              {formatDate(value)}
            </Chip>
          ))}
          {stages.map((value, index) => (
            <Chip key={`st-${index}`}>{value}</Chip>
          ))}
          {eligibility.map((value, index) => (
            <Chip key={`el-${index}`}>{value}</Chip>
          ))}
        </div>
      ) : null}
    </header>
  );
}

// --------------------------------------------------------------------------- #
// Attachments
// --------------------------------------------------------------------------- #

/**
 * Metadata-only tiles.
 *
 * `NoticeAttachment` carries filename, mimetype and size and nothing else —
 * the API has no download route (see the type's own comment), so these are
 * deliberately NOT links: a tile that looked openable and was not would be
 * worse than one that plainly is not. The type badge and the size are the
 * whole of what the feed actually knows, and that is what is printed.
 */
function AttachmentStrip({ attachments }: { attachments: NonNullable<EmailNoticeDetail['attachments']> }) {
  if (attachments.length === 0) return null;

  return (
    <section className="nd__attachments" aria-label={`Attachments (${attachments.length})`}>
      <h3 className="nd__section-title">
        <Icon name="paperclip" size={14} />
        {attachments.length === 1 ? 'Attachment' : 'Attachments'}
      </h3>
      <ul className="nd__files">
        {attachments.map((file, index) => {
          const kind = fileIconKind(file.mimetype);
          const typeLabel = fileTypeLabel(file.mimetype);
          const size = formatBytes(file.filesize);
          return (
            <li
              key={`${file.filename ?? 'attachment'}-${index}`}
              className={`nd__file nd__file--${kind}`}
              title={
                file.mimetype
                  ? `${file.filename ?? 'Attachment'} · ${file.mimetype}${size ? ` · ${size}` : ''}`
                  : file.filename ?? 'Attachment'
              }
            >
              <span className="nd__file-tile" aria-hidden="true">
                <Icon name={kind === 'archive' ? 'archive' : 'file'} size={19} />
                <span className="nd__file-kind">{typeLabel}</span>
              </span>
              <span className="nd__file-name">{file.filename ?? 'Unnamed attachment'}</span>
              {size ? <span className="nd__file-size">{size}</span> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// --------------------------------------------------------------------------- #
// Selection funnel
// --------------------------------------------------------------------------- #

function FunnelSection({ rounds }: { rounds: NoticeRoundDetail[] }) {
  const headingId = useId();
  const max = useMemo(() => rounds.reduce((peak, round) => Math.max(peak, round.count || 0), 0), [rounds]);
  if (rounds.length === 0 || max <= 0) return null;

  return (
    <section className="nd__section" aria-labelledby={headingId}>
      <h3 className="nd__section-title" id={headingId}>
        <Icon name="chart" size={14} />
        Selection funnel
      </h3>
      <ul className="nd__rounds">
        {rounds.map((round, index) => {
          const percent = Math.max(4, Math.round(((round.count || 0) / max) * 100));
          return (
            <li key={`${round.round}-${index}`} className="nd__round">
              <div className="nd__round-head">
                <span className="nd__round-name">{humanizeRound(round.round)}</span>
                <span className="nd__round-count">{(round.count || 0).toLocaleString('en-IN')}</span>
              </div>
              <div className="nd__track" aria-hidden="true">
                {/* `__fill`, not `__bar`: `__bar` is the action bar at the
                    top of this component, and the two have nothing in
                    common but the name. */}
                <div className="nd__fill" style={{ width: `${percent}%` }} />
              </div>
              {round.evidence ? (
                <p className="nd__evidence" title={round.evidence}>
                  {round.evidence}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// --------------------------------------------------------------------------- #
// Students
// --------------------------------------------------------------------------- #

const PAGE_OF_ROWS = 30;

function statusTone(status: string): PillTone {
  const value = status.trim().toLowerCase();
  if (value === 'registered') return 'green';
  if (value === 'not registered') return 'amber';
  if (value === 'waitlisted') return 'accent';
  return 'neutral';
}

/** Distinct non-null values, in first-seen order. */
function distinctValues(students: NoticeStudent[], pick: (student: NoticeStudent) => string | null): string[] {
  const seen: string[] = [];
  for (const student of students) {
    const value = (pick(student) ?? '').trim();
    if (value && !seen.includes(value)) seen.push(value);
  }
  return seen;
}

function StudentSection({ students }: { students: NoticeStudent[] }) {
  const headingId = useId();
  const searchId = useId();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [visible, setVisible] = useState(PAGE_OF_ROWS);

  const statuses = useMemo(() => distinctValues(students, (s) => s.status), [students]);
  const programValues = useMemo(() => distinctValues(students, (s) => s.program), [students]);
  const collegeValues = useMemo(() => distinctValues(students, (s) => s.college), [students]);
  const hasAnyStatus = statuses.length > 0;
  const showProgram = programValues.length >= 2;
  const showCollege = collegeValues.length >= 2;
  // A single value across every row is meta, not a column (a whole column
  // of "B.Tech" wastes the width the roll number needs).
  const constantMeta = [programValues.length === 1 ? programValues[0] : null,
    collegeValues.length === 1 ? collegeValues[0] : null].filter(Boolean).join(' · ');

  // Rows keep their original S.N. from the email, so the number never
  // changes while the user searches or filters.
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return students
      .map((student, index) => ({ student, index }))
      .filter(({ student }) => {
        if (status && (student.status ?? '').trim() !== status) return false;
        if (!needle) return true;
        return [student.rollno, student.name, student.branch, student.program, student.college, student.status]
          .some((field) => (field ?? '').toLowerCase().includes(needle));
      });
  }, [students, query, status]);

  useEffect(() => {
    setVisible(PAGE_OF_ROWS);
  }, [query, status]);

  const shown = filtered.slice(0, visible);
  const remaining = filtered.length - shown.length;

  return (
    <section className="nd__section" aria-labelledby={headingId}>
      <div className="nd__section-head">
        <h3 className="nd__section-title" id={headingId}>
          <Icon name="users" size={14} />
          Students in this email
        </h3>
        <Pill tone="accent">{students.length.toLocaleString('en-IN')} total</Pill>
        {constantMeta ? <span className="nd__meta">{constantMeta}</span> : null}
      </div>

      <div className="nd__student-tools">
        <SearchField
          id={searchId}
          value={query}
          onChange={setQuery}
          label="Search students by roll number, name or branch"
          placeholder="Search roll no, name, branch..."
        />
        {statuses.length >= 2 ? (
          <div className="nd__statuses" role="group" aria-label="Filter students by status">
            <button
              type="button"
              className={`nd__status${status === '' ? ' is-on' : ''}`}
              aria-pressed={status === ''}
              onClick={() => setStatus('')}
            >
              All
            </button>
            {statuses.map((value) => (
              <button
                key={value}
                type="button"
                className={`nd__status${status === value ? ' is-on' : ''}`}
                aria-pressed={status === value}
                onClick={() => setStatus((current) => (current === value ? '' : value))}
              >
                {value}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="nd__table-wrap">
        <table className="nd__table">
          <caption className="sr-only">
            Students named in this email, {filtered.length} matching
          </caption>
          <thead>
            {/* The `*-col` classes sit on the HEADER cells, not the data
                cells: `table-layout: fixed` measures the header row, and the
                `:has()` floor below is written against them. Dropping them
                silently collapses every optional column to its content. */}
            <tr>
              <th scope="col" className="nd__num-col">#</th>
              <th scope="col" className="nd__roll-col">Roll no</th>
              <th scope="col" className="nd__name-col">Name</th>
              <th scope="col" className="nd__branch-col">Branch</th>
              {showProgram ? <th scope="col" className="nd__program-col">Program</th> : null}
              {showCollege ? <th scope="col" className="nd__college-col">College</th> : null}
              {hasAnyStatus ? <th scope="col" className="nd__status-col">Status</th> : null}
            </tr>
          </thead>
          <tbody>
            {shown.map(({ student, index }) => (
              <tr key={`${student.rollno ?? 'x'}-${index}`}>
                <td className="nd__num-col">{index + 1}</td>
                <td className="nd__roll">{student.rollno || '—'}</td>
                <td className="nd__name">{student.name || '—'}</td>
                <td>{student.branch || '—'}</td>
                {showProgram ? <td>{student.program || '—'}</td> : null}
                {showCollege ? <td>{student.college || '—'}</td> : null}
                {hasAnyStatus ? (
                  <td>
                    {student.status?.trim() ? (
                      <Pill tone={statusTone(student.status)}>{student.status}</Pill>
                    ) : (
                      <span className="nd__dash">—</span>
                    )}
                  </td>
                ) : null}
              </tr>
            ))}
            {shown.length === 0 ? (
              <tr>
                <td
                  className="nd__empty-row"
                  colSpan={4 + (showProgram ? 1 : 0) + (showCollege ? 1 : 0) + (hasAnyStatus ? 1 : 0)}
                >
                  No student matches {query.trim() ? `"${query.trim()}"` : 'this filter'}
                  {status ? ` with status "${status}"` : ''}.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="nd__student-foot">
        <span className="nd__showing">
          Showing {shown.length.toLocaleString('en-IN')} of {filtered.length.toLocaleString('en-IN')}
        </span>
        {remaining > 0 ? (
          <>
            <Button variant="soft" size="sm" icon="chevron-down" onClick={() => setVisible((v) => v + PAGE_OF_ROWS)}>
              Show {Math.min(PAGE_OF_ROWS, remaining)} more
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setVisible(filtered.length)}>
              Show all
            </Button>
          </>
        ) : null}
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------- #
// Body
// --------------------------------------------------------------------------- #

/**
 * The raw email body, printed straight into the pane.
 *
 * No card and — this is the point — no inner scroll box. The old markup put
 * the body in a `__body-scroll` div with its own overflow, which meant the
 * pane had one scrollbar and the paragraph inside it had a second: you could
 * read a body half a screen tall with three-quarters of the pane empty, and
 * a wheel event over the text did nothing. The body is now ordinary content
 * in the pane's single scroll context, capped at the reading width below so
 * a long line cannot run the full column.
 */
function BodySection({ detail }: { detail: EmailNoticeDetail }) {
  const headingId = useId();
  const body = useMemo(() => stripEmphasis(detail.body ?? ''), [detail.body]);
  const hasBody = body.trim().length > 0;
  const truncated = (detail.bodylength ?? 0) > (detail.body ?? '').length;

  return (
    <section className="nd__body" aria-labelledby={headingId}>
      <div className="nd__section-head">
        <h3 className="nd__section-title" id={headingId}>
          <Icon name="book" size={14} />
          Email body
        </h3>
        {truncated ? (
          <span className="nd__meta">
            Showing the first {(detail.body ?? '').length.toLocaleString('en-IN')} of{' '}
            {detail.bodylength.toLocaleString('en-IN')} characters
          </span>
        ) : null}
      </div>

      {hasBody ? (
        <div className="nd__prose">
          <Prose content={body} highlight />
        </div>
      ) : (
        <p className="nd__empty">This email has no readable body text.</p>
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- #
// Panel
// --------------------------------------------------------------------------- #

interface EmailNoticeDetailProps {
  detail: EmailNoticeDetail;
  /** Clears the selection — the action bar's Back. */
  onBack: () => void;
  marks: NoticeMarks;
  onToggleStar: () => void;
  onToggleArchive: () => void;
  onToggleUnread: () => void;
}

/**
 * The reading pane for one notice: action bar, then the address block, then
 * the email itself — with the structured data (funnel, student table) below
 * it rather than above, because the thing a person opens an email to read is
 * the email.
 *
 * Every section only renders when it has data, so a plain webinar and a
 * 1,250-student shortlist share one layout without empty scaffolding.
 */
export function EmailNoticeDetail({
  detail,
  onBack,
  marks,
  onToggleStar,
  onToggleArchive,
  onToggleUnread,
}: EmailNoticeDetailProps) {
  const rounds = detail.rounds ?? [];
  const students = detail.students ?? [];
  const attachments = detail.attachments ?? [];
  const provenance = [detail.evidence ? `Parsed from: ${detail.evidence}` : null, detail.careernote ?? null]
    .filter(Boolean)
    .join(' · ');

  return (
    <article className="nd">
      <ActionBar
        detail={detail}
        marks={marks}
        onBack={onBack}
        onToggleStar={onToggleStar}
        onToggleArchive={onToggleArchive}
        onToggleUnread={onToggleUnread}
      />

      <HeaderSection detail={detail} />

      <AttachmentStrip attachments={attachments} />

      <BodySection detail={detail} />

      <FunnelSection rounds={rounds} />

      {students.length > 0 ? <StudentSection students={students} /> : null}

      {provenance ? <p className="nd__provenance">{provenance}</p> : null}
    </article>
  );
}
