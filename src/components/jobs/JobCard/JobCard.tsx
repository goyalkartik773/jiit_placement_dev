import { memo } from 'react';
import { Link } from 'react-router-dom';
import type { JobListItem } from '../../../types/job.types';
import { uniqueBy } from '../../../utils/collections';
import { excerpt, formatDate, formatINR, formatLpa, formatRelative, isPast } from '../../../utils/format';
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

/**
 * One opportunity from GET /api/jobs — calm card:
 * status dot + one neutral category tag → avatar + company name with the role
 * beneath → green package strip → location / deadline → a single accent pill
 * holding the eligibility marks → quiet excerpt → hairline footer.
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
  const deadlinePassed = isPast(job.deadline);
  const postedAt = job.posteddatetime ?? job.createdat;
  // Only "Active" carries the green indicator; every other status stays muted.
  const isActive = (job.status ?? '').trim().toLowerCase() === 'active';

  const packageValue = lpa ? `₹${lpa}` : job.packageinfo?.trim() || 'Not disclosed';
  const packageTitle = lpa ? `${formatINR(job.package)} per annum · ${tier.range}` : packageValue;

  return (
    <Card as="article" className="job-card">
      {/* 01 · status indicator + one neutral category tag + attachment count */}
      <div className="job-card__top">
        <span className={`job-card__status${isActive ? ' job-card__status--active' : ''}`}>
          <span className="job-card__status-dot" aria-hidden="true" />
          {job.status || 'Unknown'}
        </span>

        <div className="job-card__tags">
          {job.placementcategory ? (
            <Pill className="job-card__category" title={job.placementcategory}>
              {job.placementcategory}
            </Pill>
          ) : null}
          {documentCount > 0 ? (
            <span className="job-card__doc-count" title={`${documentCount} Attachments Available`}>
              <Icon name="paperclip" size={13} />
              <span className="job-card__doc-count-value">{documentCount}</span>
            </span>
          ) : null}
        </div>
      </div>

      {/* 02 · company avatar + name, role directly beneath (+ placement type) */}
      <div className="job-card__hero">
        <Avatar name={job.company} size={44} radius={11} />
        <div className="job-card__hero-text">
          <h2 className="job-card__company-name">
            <Link to={`/jobs/${job.id}`} title={job.company || undefined}>
              {job.company || 'Unknown company'}
            </Link>
          </h2>
          <p className="job-card__role" title={job.jobprofile || undefined}>
            {job.jobprofile || 'Untitled position'}
          </p>
          {job.placementtype ? (
            <span className="job-card__type" title={job.placementtype}>
              {job.placementtype}
            </span>
          ) : null}
        </div>
      </div>

      {/* 03 · package strip — green means money, muted means not disclosed */}
      <div className="job-card__package">
        <span className="job-card__package-label">Package</span>
        <span className={`job-card__package-value job-card__package-value--${tier.key}`} title={packageTitle}>
          {packageValue}
        </span>
      </div>

      {/* 04 · location left / deadline right */}
      {job.location || job.deadline ? (
        <div className="job-card__facts">
          {job.location ? (
            <IconLabel icon="pin" title={job.location} className="job-card__location">
              {job.location}
            </IconLabel>
          ) : null}
          {job.deadline ? (
            <IconLabel icon="calendar" tone={deadlinePassed ? 'danger' : 'default'} className="job-card__deadline">
              {deadlinePassed ? 'Deadline passed' : `Apply by ${formatDate(job.deadline)}`}
            </IconLabel>
          ) : null}
        </div>
      ) : null}

      {/* 05 · one accent pill holding every eligibility mark */}
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

      {/* 06 · quiet description preview */}
      {preview ? (
        <p className="job-card__excerpt">{preview}</p>
      ) : (
        <p className="job-card__excerpt job-card__excerpt--muted">No description provided.</p>
      )}

      {/* 07 · footer: posted date + View details CTA (hairline above) */}
      <footer className="job-card__footer">
        <IconLabel icon="clock" title={formatRelative(postedAt) ?? undefined}>
          {postedAt ? `Posted ${formatDate(postedAt)}` : 'Date not listed'}
        </IconLabel>
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
