import type { ReactNode } from 'react';
import { Icon, type IconName } from '../Icon/Icon';
import './StateShell.scss';

interface StateShellProps {
  icon: IconName;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: 'neutral' | 'danger';
  role?: 'status' | 'alert';
}

/** Shared visual shell for empty / error / not-found states. */
export function StateShell({ icon, title, description, action, tone = 'neutral', role = 'status' }: StateShellProps) {
  return (
    <div className={`state-shell state-shell--${tone}`} role={role}>
      <span className="state-shell__icon">
        <Icon name={icon} size={26} />
      </span>
      <h2 className="state-shell__title">{title}</h2>
      {description ? <p className="state-shell__description">{description}</p> : null}
      {action ? <div className="state-shell__action">{action}</div> : null}
    </div>
  );
}
