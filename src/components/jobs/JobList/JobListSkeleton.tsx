import { Skeleton } from '../../common/Skeleton/Skeleton';
import './JobList.scss';

function JobCardSkeleton() {
  return (
    <article className="job-card job-card--skeleton" aria-hidden="true">
      <div className="job-card__top">
        <Skeleton width="xs" height="lg" shape="pill" />
        <Skeleton width="xs" height="lg" shape="pill" />
      </div>
      <div className="job-card__hero">
        <Skeleton width="md" height="md" />
        <Skeleton width="lg" height="md" />
      </div>
      <div className="job-card__role">
        <Skeleton width="lg" height="md" />
      </div>
      <div className="job-card__package">
        <Skeleton width="md" height="sm" />
        <Skeleton width="sm" height="sm" />
      </div>
      <div className="job-card__facts">
        <Skeleton width="sm" height="sm" />
        <Skeleton width="lg" height="sm" />
      </div>
      <div className="job-card__criteria">
        <Skeleton width="md" height="sm" shape="pill" />
      </div>
      <div className="job-card__excerpt">
        <Skeleton width="full" height="sm" />
        <Skeleton width="xl" height="sm" />
        <Skeleton width="md" height="sm" />
      </div>
      <div className="job-card__divider" />
      <div className="job-card__footer">
        <Skeleton width="sm" height="sm" />
        <Skeleton width="xs" height="sm" />
      </div>
    </article>
  );
}

/** Loading placeholder mirroring the real card structure. */
export function JobListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="job-list" role="status" aria-label="Loading jobs">
      {Array.from({ length: count }, (_, index) => (
        <JobCardSkeleton key={index} />
      ))}
    </div>
  );
}
