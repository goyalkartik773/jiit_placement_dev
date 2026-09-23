import './Loader.scss';

export type LoaderSize = 'sm' | 'md' | 'lg';

interface LoaderProps {
  size?: LoaderSize;
  className?: string;
}

/** Indeterminate spinner used inside buttons and refresh indicators. */
export function Loader({ size = 'md', className }: LoaderProps) {
  return (
    <span className={['loader', `loader--${size}`, className].filter(Boolean).join(' ')} role="status" aria-label="Loading" />
  );
}
