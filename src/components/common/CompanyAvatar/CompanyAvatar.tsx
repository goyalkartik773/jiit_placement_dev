import { initials } from '../../../utils/format';
import './CompanyAvatar.scss';

interface CompanyAvatarProps {
  name: string | null | undefined;
  size?: 'md' | 'lg' | 'xl';
}

/**
 * Spec logo tile — fixed brand gradient with the company's initials,
 * derived from the `company` column (nothing is hardcoded).
 */
export function CompanyAvatar({ name, size = 'md' }: CompanyAvatarProps) {
  return (
    <span className={`company-avatar company-avatar--${size}`} aria-hidden="true">
      <span className="company-avatar__initials">{initials(name)}</span>
    </span>
  );
}
