import { Skeleton } from '../Skeleton/Skeleton';
import './ListSkeleton.scss';

interface ListSkeletonProps {
  count?: number;
  /** Accessible description of what is loading. */
  label?: string;
}

/**
 * Loading placeholder for the paged list pages (placements, email notices,
 * Superset notices) - one skeleton card per row of the real list.
 */
export function ListSkeleton({ count = 4, label = 'Loading results' }: ListSkeletonProps) {
  return (
    <div className="list-skeleton" role="status" aria-label={label}>
      {Array.from({ length: count }, (_, index) => (
        <div className="list-skeleton__card" key={index} aria-hidden="true">
          <div className="list-skeleton__head">
            <Skeleton width="md" height="md" />
            <Skeleton width="xs" height="sm" shape="pill" />
          </div>
          <Skeleton width="full" height="sm" />
          <Skeleton width="xl" height="sm" />
          <div className="list-skeleton__chips">
            <Skeleton width="sm" height="xs" shape="pill" />
            <Skeleton width="xs" height="xs" shape="pill" />
            <Skeleton width="sm" height="xs" shape="pill" />
          </div>
        </div>
      ))}
    </div>
  );
}
