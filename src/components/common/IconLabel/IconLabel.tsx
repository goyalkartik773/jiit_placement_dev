import type { ReactNode } from 'react';
import type { IconName } from '../Icon/Icon';
import { Icon } from '../Icon/Icon';
import './IconLabel.scss';

interface IconLabelProps {
  icon: IconName;
  children: ReactNode;
  title?: string;
  tone?: 'default' | 'strong' | 'danger';
  className?: string;
}

/** Icon + text metadata line, shared by job cards and the details header. */
export function IconLabel({ icon, children, title, tone = 'default', className }: IconLabelProps) {
  return (
    <span className={['icon-label', `icon-label--${tone}`, className].filter(Boolean).join(' ')} title={title}>
      <Icon name={icon} size={16} />
      <span className="icon-label__text">{children}</span>
    </span>
  );
}
