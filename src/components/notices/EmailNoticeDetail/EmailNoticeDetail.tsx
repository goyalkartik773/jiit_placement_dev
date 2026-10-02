import { useEffect, useId, useMemo, useState, type ReactNode } from 'react';
import { Icon } from '../../common/Icon/Icon';
import { Prose } from '../../common/Prose/Prose';
import { SearchField } from '../../common/SearchField/SearchField';
import { Button } from '../../common/Button/Button';
import { Pill, type PillTone } from '../../ui/Pill/Pill';
import type {
  EmailNoticeDetail,
  NoticeRoundDetail,
  NoticeStudent,
} from '../../../types/dashboard.types';
import { deadlineInfo, formatBytes, formatDate, formatDateTime } from '../../../utils/format';
import { stripEmphasis } from '../../../utils/highlight';
import './EmailNoticeDetail.scss';

// --------------------------------------------------------------------------- #
// Key details
// --------------------------------------------------------------------------- #

interface Fact {
  key: string;
  label: string;
  value: ReactNode;
  title?: string;
  /** Red value + calendar tint (a deadline that is close or gone). */
  urgent?: boolean;
  /** Spans the whole grid row (long provenance sentences, notes). */
  wide?: boolean;
}

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

function FactsSection({ detail }: { detail: EmailNoticeDetail }) {
  const headingId = useId();
  const facts: Fact[] = [];

  if (detail.sender || detail.senderemail) {
    facts.push({
      key: 'from',
      label: 'From',
      value: (
        <>
          <span className="notice-detail__strong">{detail.sender}</span>
          {detail.senderemail && detail.senderemail !== detail.sender ? (
            <span className="notice-detail__sub">{detail.senderemail}</span>
          ) : null}
        </>
      ),
      title: `${detail.sender ?? ''} <${detail.senderemail ?? ''}>`,
    });
  }
  if (detail.recipient) {
    facts.push({ key: 'to', label: 'To', value: detail.recipient, title: detail.recipient });
  }
  if (detail.cc) {
    facts.push({ key: 'cc', label: 'Cc', value: detail.cc, title: detail.cc });
  }
  if (detail.receivedat) {
    facts.push({
      key: 'received',
      label: 'Received',
      value: <span className="notice-detail__num">{formatDateTime(detail.receivedat)}</span>,
    });
  }

  const conf = confidenceLabel(detail.confidence, detail.method);
  facts.push({
    key: 'type',
    label: 'Type',
    value: (
      <>
        <span className="notice-detail__strong">{detail.classificationlabel}</span>
        {conf ? <span className="notice-detail__sub">{conf}</span> : null}
      </>
    ),
    title: detail.classification,
  });

  if (detail.company) {
    facts.push({ key: 'company', label: 'Company', value: detail.company });
  }
  if (detail.headline) {
    facts.push({
      key: 'headline',
      label: 'Headline',
      value: detail.headline,
      title:
        detail.stageraw && detail.stageraw !== detail.headline
          ? `As worded in the email: ${detail.stageraw}`
          : undefined,
    });
  }

  const deadline = deadlineInfo(detail.deadline);
  if (deadline || detail.deadline) {
    facts.push({
      key: 'deadline',
      label: 'Deadline',
      value: (
        <span className="notice-detail__num">{deadline ? deadline.text : formatDate(detail.deadline)}</span>
      ),
      title: detail.deadline ?? undefined,
      urgent: deadline?.urgent ?? false,
    });
  }

  const interviewDates = Array.isArray(detail.interviewdates) ? detail.interviewdates : [];
  if (interviewDates.length > 0) {
    facts.push({
      key: 'interviews',
      label: interviewDates.length === 1 ? 'Interview date' : 'Interview dates',
      value: (
        <span className="notice-detail__chips">
          {interviewDates.map((value, index) => (
            <span key={index} className="notice-detail__chip" title={value}>
              <Icon name="calendar" size={13} />
              {formatDate(value)}
            </span>
          ))}
        </span>
      ),
    });
  }

  if (detail.stages && detail.stages.length > 0) {
    facts.push({
      key: 'stages',
      label: 'Rounds',
      value: (
        <span className="notice-detail__chips">
          {detail.stages.map((value, index) => (
            <span key={index} className="notice-detail__chip">
              {value}
            </span>
          ))}
        </span>
      ),
    });
  }

  if (detail.eligibility && detail.eligibility.length > 0) {
    facts.push({
      key: 'eligibility',
      label: 'Eligibility',
      value: (
        <span className="notice-detail__chips">
          {detail.eligibility.map((value, index) => (
            <span key={index} className="notice-detail__chip">
              {value}
            </span>
          ))}
        </span>
      ),
      wide: true,
    });
  }

  if (detail.link) {
    facts.push({
      key: 'link',
      label: 'Registration',
      value: (
        <a
          className="notice-detail__link"
          href={detail.link}
          target="_blank"
          rel="noopener noreferrer"
          title={detail.link}
        >
          Open registration link
          <Icon name="external-link" size={13} />
        </a>
      ),
    });
  }

  const attachments = Array.isArray(detail.attachments) ? detail.attachments : [];
  if (attachments.length > 0) {
    facts.push({
      key: 'attachments',
      label: attachments.length === 1 ? 'Attachment' : 'Attachments',
      value: (
        <span className="notice-detail__chips">
          {attachments.map((file, index) => (
            <span
              key={index}
              className="notice-detail__chip"
              title={file.mimetype ? `${file.filename ?? 'Attachment'} · ${file.mimetype}` : undefined}
            >
              <Icon name="file" size={13} />
              {file.filename ?? 'Unnamed attachment'}
              {file.filesize ? <span className="notice-detail__chip-meta">{formatBytes(file.filesize)}</span> : null}
            </span>
          ))}
        </span>
      ),
      wide: true,
    });
  }

  if (detail.careernote) {
    facts.push({
      key: 'careernote',
      label: 'Note',
      value: detail.careernote,
      wide: true,
    });
  }
  if (detail.evidence) {
    facts.push({
      key: 'evidence',
      label: 'Parsed from',
      value: detail.evidence,
      wide: true,
    });
  }

  if (facts.length === 0) return null;

  return (
    <section className="notice-detail__section" aria-labelledby={headingId}>
      <h4 className="notice-detail__heading" id={headingId}>
        <Icon name="info" size={14} />
        Key details
      </h4>
      <dl className="notice-detail__facts">
        {facts.map((fact) => (
          <div
            key={fact.key}
            className={[
              'notice-detail__fact',
              fact.wide ? ' notice-detail__fact--wide' : '',
              fact.urgent ? ' notice-detail__fact--urgent' : '',
            ].join('')}
            title={fact.title}
          >
            <dt className="notice-detail__label">{fact.label}</dt>
            <dd className="notice-detail__value">{fact.value}</dd>
          </div>
        ))}
      </dl>
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
    <section className="notice-detail__section" aria-labelledby={headingId}>
      <h4 className="notice-detail__heading" id={headingId}>
        <Icon name="chart" size={14} />
        Selection funnel
      </h4>
      <ul className="notice-detail__rounds">
        {rounds.map((round, index) => {
          const percent = Math.max(4, Math.round(((round.count || 0) / max) * 100));
          return (
            <li key={`${round.round}-${index}`} className="notice-detail__round">
              <div className="notice-detail__round-head">
                <span className="notice-detail__round-name">{humanizeRound(round.round)}</span>
                <span className="notice-detail__round-count">{(round.count || 0).toLocaleString('en-IN')}</span>
              </div>
              <div className="notice-detail__track" aria-hidden="true">
                <div className="notice-detail__bar" style={{ width: `${percent}%` }} />
              </div>
              {round.evidence ? (
                <p className="notice-detail__evidence" title={round.evidence}>
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
    <section className="notice-detail__section" aria-labelledby={headingId}>
      <div className="notice-detail__section-head">
        <h4 className="notice-detail__heading" id={headingId}>
          <Icon name="users" size={14} />
          Students in this email
        </h4>
        <Pill tone="accent">{students.length.toLocaleString('en-IN')} total</Pill>
        {constantMeta ? <span className="notice-detail__meta">{constantMeta}</span> : null}
      </div>

      <div className="notice-detail__student-tools">
        <SearchField
          id={searchId}
          value={query}
          onChange={setQuery}
          label="Search students by roll number, name or branch"
          placeholder="Search roll no, name, branch..."
        />
        {statuses.length >= 2 ? (
          <div className="notice-detail__statuses" role="group" aria-label="Filter students by status">
            <button
              type="button"
              className={`notice-detail__status${status === '' ? ' is-on' : ''}`}
              aria-pressed={status === ''}
              onClick={() => setStatus('')}
            >
              All
            </button>
            {statuses.map((value) => (
              <button
                key={value}
                type="button"
                className={`notice-detail__status${status === value ? ' is-on' : ''}`}
                aria-pressed={status === value}
                onClick={() => setStatus((current) => (current === value ? '' : value))}
              >
                {value}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="notice-detail__table-wrap">
        <table className="notice-detail__table">
          <caption className="sr-only">
            Students named in this email, {filtered.length} matching
          </caption>
          <thead>
            <tr>
              <th scope="col" className="notice-detail__num-col">
                #
              </th>
              <th scope="col">Roll no</th>
              <th scope="col">Name</th>
              <th scope="col">Branch</th>
              {showProgram ? <th scope="col">Program</th> : null}
              {showCollege ? <th scope="col">College</th> : null}
              {hasAnyStatus ? <th scope="col">Status</th> : null}
            </tr>
          </thead>
          <tbody>
            {shown.map(({ student, index }) => (
              <tr key={`${student.rollno ?? 'x'}-${index}`}>
                <td className="notice-detail__num-col">{index + 1}</td>
                <td className="notice-detail__roll">{student.rollno || '—'}</td>
                <td className="notice-detail__name">{student.name || '—'}</td>
                <td>{student.branch || '—'}</td>
                {showProgram ? <td>{student.program || '—'}</td> : null}
                {showCollege ? <td>{student.college || '—'}</td> : null}
                {hasAnyStatus ? (
                  <td>
                    {student.status?.trim() ? (
                      <Pill tone={statusTone(student.status)}>{student.status}</Pill>
                    ) : (
                      <span className="notice-detail__dash">—</span>
                    )}
                  </td>
                ) : null}
              </tr>
            ))}
            {shown.length === 0 ? (
              <tr>
                <td
                  className="notice-detail__empty-row"
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

      <div className="notice-detail__student-foot">
        <span className="notice-detail__showing">
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

function BodySection({ detail }: { detail: EmailNoticeDetail }) {
  const headingId = useId();
  const body = useMemo(() => stripEmphasis(detail.body ?? ''), [detail.body]);
  const hasBody = body.trim().length > 0;
  const truncated = (detail.bodylength ?? 0) > (detail.body ?? '').length;

  return (
    <section className="notice-detail__section" aria-labelledby={headingId}>
      <div className="notice-detail__section-head">
        <h4 className="notice-detail__heading" id={headingId}>
          <Icon name="book" size={14} />
          Email body
        </h4>
        {truncated ? (
          <span className="notice-detail__meta">
            Showing the first {(detail.body ?? '').length.toLocaleString('en-IN')} of{' '}
            {detail.bodylength.toLocaleString('en-IN')} characters
          </span>
        ) : null}
      </div>

      {hasBody ? (
        <div className="notice-detail__body-scroll">
          <Prose content={body} highlight className="notice-detail__body" />
        </div>
      ) : (
        <p className="notice-detail__empty">This email has no readable body text.</p>
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- #
// Panel
// --------------------------------------------------------------------------- #

interface EmailNoticeDetailProps {
  detail: EmailNoticeDetail;
}

/**
 * The expanded "Read more" panel of one email notice: structured data first
 * (key details, funnel bars, the student table), the raw email body last -
 * highlighted so money, dates and action words read at a glance.
 *
 * Every section only renders when it has data, so a plain webinar and a
 * 1,250-student shortlist share the same layout without empty scaffolding.
 */
export function EmailNoticeDetail({ detail }: EmailNoticeDetailProps) {
  const rounds = detail.rounds ?? [];
  const students = detail.students ?? [];

  return (
    <div className="notice-detail">
      <FactsSection detail={detail} />
      <FunnelSection rounds={rounds} />
      {students.length > 0 ? <StudentSection students={students} /> : null}
      <BodySection detail={detail} />
    </div>
  );
}
