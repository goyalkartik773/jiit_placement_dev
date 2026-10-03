import { memo } from 'react';
import { Link } from 'react-router-dom';
import type { JobListItem } from '../../../types/job.types';
import { uniqueBy } from '../../../utils/collections';
import {
  daysUntil,
  excerpt,
  formatDate,
  formatINR,
  formatLpa,
  formatRelative,
} from '../../../utils/format';
import { stripHtml } from '../../../utils/html';
import { getPackageTier } from '../../../utils/tiers';
import { Icon } from '../../common/Icon/Icon';
import { IconLabel } from '../../common/IconLabel/IconLabel';
import { Avatar } from '../../ui/Avatar/Avatar';
import { Card } from '../../ui/Card/Card';
import { Pill } from '../../ui/Pill/Pill';
import { CriteriaChip } from '../CriteriaChip/CriteriaChip';
import './JobCard.scss';

interface JobCardProps {
  job: JobListItem;
}

type DeadlineState = 'open' | 'closing' | 'closed';

/**
 * Days remaining → one of three readable states:
 * open (more than a week) / closing soon (inside a week) / closed (past).
 *
 * Takes the ALREADY-COMPUTED day count rather than the raw string, so the
 * badge and the footer's "Apply by … / Closed …" can never disagree. They
 * used to be derived separately — `isPast()` compares timestamps, so a
 * date-only deadline of *today* read as past the moment midnight passed while
 * `daysUntil()` still counted it as 0, and a card could say CLOSING SOON
 * above Closed today below.
 *
 * A job with no deadline gets NO badge rather than an inferred one: there is
 * nothing to be open or closed against, and inventing a state here would
 * contradict the status dot two elements to its left.
 */
function deadlineStateOf(days: number | null): DeadlineState | null {
  if (days === null) return null;
  if (days < 0) return 'closed';
  if (days <= 7) return 'closing';
  return 'open';
}

/**
 * One opportunity from GET /api/jobs — five blocks, in scanning order:
 *
 *   01 meta      status + category left · deadline state + attachments right
 *   02 identity  avatar + company/role/meta left · package figure right
 *   03 criteria  the eligibility marks
 *   04 excerpt   the description, as plain text (no box)
 *   05 footer    posted + apply-by dates · View details
 *
 * Every string comes from the jobs-table response (nothing hardcoded).
 */
function JobCardComponent({ job }: JobCardProps) {
  const description = stripHtml(job.jobdescription) || stripHtml(job.content);
  const preview = excerpt(description, 190);
  const lpa = formatLpa(job.package);
  const tier = getPackageTier(job.package);
  const marks = uniqueBy(
    Array.isArray(job.eligiblitymarks) ? job.eligiblitymarks.filter(Boolean) : [],
    (mark) => `${mark.level}|${mark.criteria}`,
  );
  const documentCount = Array.isArray(job.documents) ? job.documents.filter(Boolean).length : 0;
  const deadlineDays = daysUntil(job.deadline);
  const deadlineClosed = deadlineDays !== null && deadlineDays < 0;
  const deadlineState = deadlineStateOf(deadlineDays);
  const postedAt = job.posteddatetime ?? job.createdat;
  // Only "Active" carries the green indicator; every other status stays muted.
  const isActive = (job.status ?? '').trim().toLowerCase() === 'active';

  const packageValue = lpa ? `₹${lpa}` : job.packageinfo?.trim() || 'Not disclosed';
  const packageTitle = lpa ? `${formatINR(job.package)} per annum · ${tier.range}` : packageValue;

  // Placement type, category and location collapse into ONE quiet line. They
  // used to occupy a dedicated facts row alongside the deadline; the deadline
  // moved up to the state badge, so only the placement facts need a home.
  const metaLine = [job.placementtype, job.placementcategory, job.location]
    .filter((part): part is string => Boolean(part && part.trim()))
    .join(' · ');

  return (
    <Card as="article" className="job-card">
      {/* 01 · status · deadline state + attachments */}
      <div className="job-card__top">
        <span className={`job-card__status${isActive ? ' job-card__status--active' : ''}`}>
          <span className="job-card__status-dot" aria-hidden="true" />
          {job.status || 'Unknown'}
        </span>

        <span className="job-card__top-right">
          {deadlineState ? (
            <span
              className={`job-card__deadline-badge job-card__deadline-badge--${deadlineState}`}
              title={job.deadline ? `Apply by ${formatDate(job.deadline)}` : undefined}
            >
              {deadlineState === 'open' ? 'OPEN' : deadlineState === 'closing' ? 'CLOSING SOON' : 'CLOSED'}
            </span>
          ) : null}
          {documentCount > 0 ? (
            <span className="job-card__doc-count" title={`${documentCount} Attachments Available`}>
              <Icon name="paperclip" size={13} />
              <span className="job-card__doc-count-value">{documentCount}</span>
            </span>
          ) : null}
        </span>
      </div>

      {/* 02 · identity left, the package figure right */}
      <div className="job-card__hero">
        <Avatar name={job.company} size={42} radius={8} />
        <div className="job-card__hero-text">
          <h2 className="job-card__company-name">
            <Link to={`/jobs/${job.id}`} title={job.company || undefined}>
              {job.company || 'Unknown company'}
            </Link>
          </h2>
          {/* Three levels, in order of what a scanner needs: who → what →
              where/kind. The role keeps its own line because it is the job
              title; burying it in the meta line made it read as a tag. */}
          <p className="job-card__role" title={job.jobprofile || undefined}>
            {job.jobprofile || 'Untitled position'}
          </p>
          {metaLine ? (
            <p className="job-card__meta" title={metaLine}>
              {metaLine}
            </p>
          ) : null}
        </div>

        <div className="job-card__package">
          <span className="job-card__package-label">Package</span>
          <span className={`job-card__package-value job-card__package-value--${tier.key}`} title={packageTitle}>
            {packageValue}
          </span>
        </div>
      </div>

      {/* 03 · one accent pill holding every eligibility mark */}
      {marks.length > 0 ? (
        <div className="job-card__criteria" aria-label="Eligibility criteria">
          <Pill tone="accent" className="job-card__eligibility">
            {marks.slice(0, 3).map((mark) => (
              <CriteriaChip key={mark.id} mark={mark} />
            ))}
            {marks.length > 3 ? <span className="job-card__more">+{marks.length - 3} more</span> : null}
          </Pill>
        </div>
      ) : null}

      {/* 04 · description preview — plain text, no box */}
      {preview ? (
        <p className="job-card__excerpt">{preview}</p>
      ) : (
        <p className="job-card__excerpt job-card__excerpt--muted">No description provided.</p>
      )}

      {/* 05 · footer: posted + apply-by, and the way in */}
      <footer className="job-card__footer">
        <span className="job-card__dates">
          <IconLabel icon="clock" title={formatRelative(postedAt) ?? undefined}>
            {postedAt ? `Posted ${formatDate(postedAt)}` : 'Date not listed'}
          </IconLabel>
          {job.deadline ? (
            <>
              <span className="job-card__date-sep" aria-hidden="true">
                ·
              </span>
              <span className="job-card__apply-by">
                {deadlineClosed ? `Closed ${formatDate(job.deadline)}` : `Apply by ${formatDate(job.deadline)}`}
              </span>
            </>
          ) : null}
        </span>
        <Link className="job-card__cta" to={`/jobs/${job.id}`}>
          View details
          <Icon name="chevron-right" size={14} />
        </Link>
      </footer>
    </Card>
  );
}

/** Memoized: list of up to 100 cards re-renders only when its job changes. */
export const JobCard = memo(JobCardComponent);
