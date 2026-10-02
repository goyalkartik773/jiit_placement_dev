import type { FocusEvent, MouseEvent as ReactMouseEvent, ReactNode } from 'react';
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
  /** Focus left the button (e.g. an armed action disarming on blur). */
  onBlur?: (event: FocusEvent<HTMLButtonElement>) => void;
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
  /**
   * The event is passed through (rather than `() => void`) so a caller can
   * read `currentTarget` — that is how a dialog knows which control opened it
   * and returns focus there on close. Every `() => void` handler already
   * satisfies this signature, so nothing that exists today has to change.
   */
  onClick?: (event: ReactMouseEvent<HTMLButtonElement>) => void;
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
  onBlur,
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
      onBlur={onBlur}
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
