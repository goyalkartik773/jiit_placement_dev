import { memo } from 'react';
import { Link } from 'react-router-dom';
import type { JobListItem } from '../../../types/job.types';
import { uniqueBy } from '../../../utils/collections';
import { excerpt, formatDate, formatINR, formatLpa, formatRelative, isPast } from '../../../utils/format';
import { stripHtml } from '../../../utils/html';
import { getPackageTier } from '../../../utils/tiers';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Chip } from '../../common/Chip/Chip';
import { CompanyAvatar } from '../../common/CompanyAvatar/CompanyAvatar';
import { Icon } from '../../common/Icon/Icon';
import { IconLabel } from '../../common/IconLabel/IconLabel';
import { CriteriaChip } from '../CriteriaChip/CriteriaChip';
import './JobCard.scss';

interface JobCardProps {
  job: JobListItem;
}

/**
 * One opportunity from GET /api/jobs — spec card:
 * status/category pills + attachments → company hero (gradient tile,
 * name, placement type when present) → "Role:" line → package bar →
 * location/deadline → criteria chips → excerpt → dashed footer.
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

  const packageValue = lpa ? `₹${lpa}` : job.packageinfo?.trim() || 'Not disclosed';
  const packageTitle = lpa ? `${formatINR(job.package)} per annum · ${tier.range}` : packageValue;

  return (
    <article className="job-card">
      {/* 01 · status + category pills, attachment count */}
      <div className="job-card__top">
        <div className="job-card__tags">
          <Badge tone={statusTone(job.status)} dot>
            {job.status || 'Unknown'}
          </Badge>
          {job.placementcategory ? (
            <Chip tone="accent" title={job.placementcategory}>
              {job.placementcategory}
            </Chip>
          ) : null}
        </div>
        {documentCount > 0 ? (
          <span className="job-card__doc-count" title={`${documentCount} Attachments Available`}>
            <Icon name="paperclip" size={14} />
            <span className="job-card__doc-count-value">{documentCount}</span>
          </span>
        ) : null}
      </div>

      {/* 02 · company hero — gradient tile + name (+ placement type when present) */}
      <div className="job-card__hero">
        <CompanyAvatar name={job.company} />
        <div className="job-card__hero-text">
          <h2 className="job-card__company-name">
            <Link to={`/jobs/${job.id}`} title={job.company || undefined}>
              {job.company || 'Unknown company'}
            </Link>
          </h2>
          {job.placementtype ? (
            <span className="job-card__type" title={job.placementtype}>
              {job.placementtype}
            </span>
          ) : null}
        </div>
      </div>

      {/* 03 · role line (jobs.jobprofile) */}
      <p className="job-card__role">
        <span className="job-card__role-label">Role:</span>
        <span className="job-card__role-value" title={job.jobprofile || undefined}>
          {job.jobprofile || 'Untitled position'}
        </span>
      </p>

      {/* 04 · compensation bar */}
      <div className="job-card__package">
        <span className="job-card__package-label">Package</span>
        <span className={`job-card__package-value job-card__package-value--${tier.key}`} title={packageTitle}>
          {packageValue}
        </span>
      </div>

      {/* 05 · location left / deadline right */}
      {job.location || job.deadline ? (
        <div className="job-card__facts">
          {job.location ? (
            <IconLabel icon="pin" title={job.location}>
              {job.location}
            </IconLabel>
          ) : null}
          {job.deadline ? (
            <IconLabel icon="calendar" tone={deadlinePassed ? 'danger' : 'default'}>
              {deadlinePassed ? 'Deadline passed' : `Apply by ${formatDate(job.deadline)}`}
            </IconLabel>
          ) : null}
        </div>
      ) : null}

      {/* 06 · strictness-colored eligibility chips */}
      {marks.length > 0 ? (
        <div className="job-card__criteria" aria-label="Eligibility criteria">
          {marks.slice(0, 3).map((mark) => (
            <CriteriaChip key={mark.id} mark={mark} />
          ))}
          {marks.length > 3 ? <Chip tone="muted">+{marks.length - 3} more</Chip> : null}
        </div>
      ) : null}

      {/* 07 · description preview */}
      {preview ? (
        <p className="job-card__excerpt">{preview}</p>
      ) : (
        <p className="job-card__excerpt job-card__excerpt--muted">No description provided.</p>
      )}

      {/* 08 · spec dashed divider */}
      <div className="job-card__divider" aria-hidden="true" />

      {/* 09 · footer: posted date + View details CTA */}
      <footer className="job-card__footer">
        <IconLabel icon="clock" title={formatRelative(postedAt) ?? undefined}>
          {postedAt ? `Posted ${formatDate(postedAt)}` : 'Date not listed'}
        </IconLabel>
        <Link className="job-card__cta" to={`/jobs/${job.id}`}>
          View details
          <Icon name="chevron-right" size={16} />
        </Link>
      </footer>
    </article>
  );
}

/** Memoized: list of up to 100 cards re-renders only when its job changes. */
export const JobCard = memo(JobCardComponent);
