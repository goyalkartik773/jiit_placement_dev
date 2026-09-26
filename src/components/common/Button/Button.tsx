import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Icon, type IconName } from '../Icon/Icon';
import { Loader, type LoaderSize } from '../Loader/Loader';
import './Button.scss';

export type ButtonVariant = 'primary' | 'soft' | 'ghost' | 'danger';
export type ButtonSize = 'md' | 'sm';

interface ButtonBaseProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  children: ReactNode;
  className?: string;
  title?: string;
  disabled?: boolean;
}

function classesFor(variant: ButtonVariant, size: ButtonSize, className?: string): string {
  return ['btn', `btn--${variant}`, `btn--${size}`, className].filter(Boolean).join(' ');
}

function loaderSizeFor(size: ButtonSize): LoaderSize {
  return size === 'sm' ? 'sm' : 'md';
}

interface ButtonProps extends ButtonBaseProps {
  type?: 'button' | 'submit';
  loading?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
}

/** Standard action button. Presentation only — behaviour is passed in. */
export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  loading = false,
  disabled,
  type = 'button',
  onClick,
  className,
  title,
  ariaLabel,
  children,
}: ButtonProps) {
  return (
    <button
      type={type}
      className={classesFor(variant, size, className)}
      disabled={disabled || loading}
      onClick={onClick}
      title={title}
      aria-label={ariaLabel}
      aria-busy={loading || undefined}
    >
      {loading ? <Loader size={loaderSizeFor(size)} /> : icon ? <Icon name={icon} size={size === 'sm' ? 14 : 16} /> : null}
      {children}
    </button>
  );
}

interface ButtonLinkProps extends ButtonBaseProps {
  to: string;
  ariaLabel?: string;
}

/** Navigation styled as a button (real <a>/<Link> semantics for accessibility). */
export function ButtonLink({ to, variant = 'primary', size = 'md', icon, className, title, ariaLabel, children }: ButtonLinkProps) {
  return (
    <Link to={to} className={classesFor(variant, size, className)} title={title} aria-label={ariaLabel}>
      {icon ? <Icon name={icon} size={size === 'sm' ? 14 : 16} /> : null}
      {children}
    </Link>
  );
}
