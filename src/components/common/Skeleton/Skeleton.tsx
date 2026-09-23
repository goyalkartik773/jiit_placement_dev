import './Skeleton.scss';

export type SkeletonWidth = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'full';
export type SkeletonHeight = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface SkeletonProps {
  width?: SkeletonWidth;
  height?: SkeletonHeight;
  shape?: 'rect' | 'pill' | 'circle';
  className?: string;
}

/**
 * Skeleton primitive. All sizing comes from design-token-backed modifier
 * classes — no inline styles.
 */
export function Skeleton({ width = 'full', height = 'sm', shape = 'rect', className }: SkeletonProps) {
  const classes = ['skeleton', `skeleton--w-${width}`, `skeleton--h-${height}`, `skeleton--${shape}`, className]
    .filter(Boolean)
    .join(' ');
  return <span className={classes} aria-hidden="true" />;
}
