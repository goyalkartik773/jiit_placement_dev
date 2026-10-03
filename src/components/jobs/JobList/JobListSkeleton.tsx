import { Skeleton } from '../../common/Skeleton/Skeleton';
import './JobList.scss';

/**
 * Loading placeholder mirroring the real card's five blocks in the same order
 * and at close to the same heights: meta line → identity + package → criteria
 * → excerpt → footer.
 *
 * Two slots need pinning by hand because `Skeleton`'s width scale is a
 * PERCENTAGE of the parent: the avatar slot resolved to 55% (181px) where the
 * real `Avatar` is 42px, and the package column is shrink-to-fit, so a
 * percentage inside it resolved to 0 and collapsed entirely. Matching the
 * structure is what stops the grid jumping when the data lands.
 */
function JobCardSkeleton() {
  return (
    <article className="job-card job-card--skeleton" aria-hidden="true">
      <div className="job-card__top">
        <Skeleton width="xs" height="lg" shape="pill" />
        <span className="job-card__top-right">
          <Skeleton width="xs" height="lg" shape="pill" />
          <Skeleton width="xs" height="sm" />
        </span>
      </div>

      <div className="job-card__hero">
        <Skeleton className="job-card__avatar-skel" width="md" height="md" />
        <div className="job-card__hero-text">
          {/* company (23px line) → role (17) → meta (14): the real card's
              21 / 19 / 18 with its 3px column gaps */}
          <Skeleton width="lg" height="lg" />
          <Skeleton width="xl" height="md" />
          <Skeleton width="md" height="sm" />
        </div>
        <div className="job-card__package">
          <Skeleton width="xs" height="xs" />
          <Skeleton width="md" height="lg" />
        </div>
      </div>

      <div className="job-card__criteria">
        <span className="job-card__eligibility job-card__eligibility--skel">
          <Skeleton width="md" height="md" shape="pill" />
        </span>
      </div>

      <div className="job-card__excerpt">
        <Skeleton width="full" height="sm" />
        <Skeleton width="xl" height="sm" />
        <Skeleton width="md" height="sm" />
      </div>

      {/* `.job-card__dates` wraps to two lines in the real card (posted +
          apply-by over 227px against a 94px CTA), so it wraps here too */}
      <div className="job-card__footer">
        <span className="job-card__dates">
          <Skeleton width="lg" height="md" />
          <Skeleton width="md" height="md" />
        </span>
        <Skeleton width="xs" height="sm" />
      </div>
    </article>
  );
}

/** Loading placeholder for the grid. */
export function JobListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="job-list" role="status" aria-label="Loading jobs">
      {Array.from({ length: count }, (_, index) => (
        <JobCardSkeleton key={index} />
      ))}
    </div>
  );
}
