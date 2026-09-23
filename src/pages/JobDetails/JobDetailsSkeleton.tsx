import { Skeleton } from '../../components/common/Skeleton/Skeleton';

/** Loading placeholder mirroring the details layout (bar + hero + bento + split). */
export function JobDetailsSkeleton() {
  return (
    <div className="detail-skeleton" role="status" aria-label="Loading job details">
      {/* Breadcrumb bar */}
      <div className="detail-skeleton__bar">
        <Skeleton width="sm" height="sm" />
        <Skeleton width="md" height="sm" shape="pill" />
      </div>

      {/* Hero */}
      <div className="detail-skeleton__hero">
        <Skeleton width="xs" height="lg" shape="pill" />
        <div className="detail-skeleton__identity">
          <Skeleton width="md" height="xl" />
          <div className="detail-skeleton__identity-lines">
            <Skeleton width="lg" height="xl" />
            <Skeleton width="sm" height="sm" />
          </div>
        </div>
        <Skeleton width="sm" height="md" />
        <Skeleton width="full" height="sm" />
        <Skeleton width="xl" height="sm" />
      </div>

      {/* Bento metrics */}
      <div className="detail-skeleton__metrics">
        {[0, 1, 2, 3].map((index) => (
          <div className="detail-skeleton__metric" key={index}>
            <Skeleton width="sm" height="xs" />
            <Skeleton width="md" height="lg" />
            <Skeleton width="full" height="xs" />
          </div>
        ))}
      </div>

      {/* Two columns */}
      <div className="detail-skeleton__columns">
        <div className="detail-skeleton__card">
          <Skeleton width="md" height="md" />
          <Skeleton width="full" height="sm" />
          <Skeleton width="xl" height="sm" />
          <Skeleton width="lg" height="sm" />
          <Skeleton width="full" height="sm" />
        </div>
        <div className="detail-skeleton__card">
          <Skeleton width="sm" height="md" />
          {[0, 1, 2, 3, 4].map((index) => (
            <Skeleton key={index} width="full" height="sm" />
          ))}
        </div>
      </div>
    </div>
  );
}
