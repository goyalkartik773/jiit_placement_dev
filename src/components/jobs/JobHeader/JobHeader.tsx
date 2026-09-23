import { Link } from 'react-router-dom';
import type { JobDetail } from '../../../types/job.types';
import { excerpt, formatDate, formatRelative, isPast } from '../../../utils/format';
import { stripHtml } from '../../../utils/html';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { CompanyAvatar } from '../../common/CompanyAvatar/CompanyAvatar';
import { Icon } from '../../common/Icon/Icon';
import './JobHeader.scss';

interface JobHeaderProps {
  job: JobDetail;
}

/**
 * Details page top region (spec): breadcrumb bar (back + status/posted
 * badges) over a hero surface with ambient gradient blobs — category/code/
 * open chips, company identity, target role, and an aside holding the
 * deadline panel + jump-to-documents CTA. Pure API data; 0/null values
 * fall back to "Not disclosed".
 */
export function JobHeader({ job }: JobHeaderProps) {
  const deadlinePassed = job.deadline ? isPast(job.deadline) : false;
  const deadlineRel = job.deadline ? formatRelative(job.deadline) : null;
  const postedAt = job.posteddatetime ?? job.createdat;
  const postedRel = formatRelative(postedAt);
  const documentCount = Array.isArray(job.documents) ? job.documents.filter(Boolean).length : 0;
  const descriptionText = stripHtml(job.jobdescription || job.content);
  const summary = excerpt(descriptionText, 150);

  return (
    <header className="job-header">
      {/* Breadcrumb bar: back + badges */}
      <div className="job-header__bar">
        <Link to="/" className="job-header__back">
          <Icon name="arrow-left" size={16} />
          <span>All Jobs</span>
        </Link>

        <div className="job-header__badges">
          <Badge tone={statusTone(job.status)} dot>
            {job.status || 'Unknown'}
          </Badge>
          {postedAt ? (
            <span className="job-header__posted">
              Posted {formatDate(postedAt)}
              {postedRel ? <span className="job-header__posted-rel"> · {postedRel}</span> : null}
            </span>
          ) : null}
        </div>
      </div>

      {/* Hero surface */}
      <div className="job-header__hero">
        <div className="job-header__main">
          <div className="job-header__chips">
            {job.placementcategory ? (
              <span className="job-header__chip job-header__chip--neutral" title={job.placementcategory}>
                <span className="job-header__chip-text">{job.placementcategory}</span>
              </span>
            ) : null}
            {job.placementcategorycode ? (
              <span className="job-header__chip job-header__chip--code">
                <Icon name="briefcase" size={12} />
                Code {job.placementcategorycode}
              </span>
            ) : null}
            {job.deadline ? (
              <span
                className={[
                  'job-header__chip',
                  deadlinePassed ? 'job-header__chip--danger' : 'job-header__chip--success',
                ].join(' ')}
              >
                {deadlinePassed ? null : <span className="job-header__chip-dot" aria-hidden="true" />}
                {deadlinePassed ? 'Drive Closed' : 'Open'}
              </span>
            ) : null}
          </div>

          <div className="job-header__identity">
            <CompanyAvatar name={job.company} size="xl" />
            <div className="job-header__identity-text">
              <h1 className="job-header__company" title={job.company || undefined}>
                {job.company || 'Unknown company'}
              </h1>
              <span className="job-header__location" title={job.location || undefined}>
                <Icon name="pin" size={14} />
                {job.location || 'Location not specified'}
              </span>
            </div>
          </div>

          <div className="job-header__role">
            <span className="job-header__role-label">
              Target Role
              {job.placementtype ? (
                <>
                  <span className="job-header__role-sep" aria-hidden="true">
                    ·
                  </span>
                  <span className="job-header__role-type" title={job.placementtype}>
                    {job.placementtype}
                  </span>
                </>
              ) : null}
            </span>

            <h2 className="job-header__profile" title={job.jobprofile || undefined}>
              {job.jobprofile || 'Untitled position'}
            </h2>

            {summary ? (
              <p className="job-header__summary" title={descriptionText || undefined}>
                {summary}
              </p>
            ) : null}
          </div>
        </div>

        {/* Aside — deadline panel + documents CTA */}
        <div className="job-header__aside">
          <div
            className={[
              'job-header__deadline',
              deadlinePassed ? 'job-header__deadline--passed' : null,
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <span className="job-header__deadline-label">
              {job.deadline ? (deadlinePassed ? 'Drive Closed' : 'Registration Closes') : 'Deadline'}
            </span>
            <span className="job-header__deadline-value">
              {job.deadline ? formatDate(job.deadline) : 'Not disclosed'}
            </span>
            {deadlineRel ? <span className="job-header__deadline-sub">{deadlineRel}</span> : null}
          </div>

          <Button
            variant="soft"
            size="md"
            icon="folder"
            className="job-header__docs-btn"
            onClick={() => document.getElementById('drive-documents')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          >
            View Documents ({documentCount})
          </Button>
        </div>
      </div>
    </header>
  );
}
