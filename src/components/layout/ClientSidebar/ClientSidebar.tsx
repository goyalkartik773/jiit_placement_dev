import { useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Icon, type IconName } from '../../common/Icon/Icon';
import './ClientSidebar.scss';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  /** Exact-match routes (a prefix match would light up two items). */
  end?: boolean;
}

/** Client navigation, in product order. Admin lives in its own shell. */
const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: 'home', end: true },
  { to: '/analytics', label: 'Analytics', icon: 'chart', end: true },
  { to: '/jobs', label: 'Active Job Listing', icon: 'briefcase' },
  { to: '/placements', label: 'Company-Wise Placement', icon: 'building' },
  { to: '/email-notices', label: 'Email Notices', icon: 'inbox' },
  { to: '/superset-notices', label: 'Superset Notices', icon: 'bell' },
];

interface ClientSidebarProps {
  /** Drawer state — only meaningful below the drawer breakpoint. */
  open: boolean;
  onClose: () => void;
}

/**
 * Left navigation rail of the client shell.
 *
 * Layout by viewport:
 *   ≥1024px  full rail — product mark, icon + label items
 *   768–1023 icon-only rail (labels collapse, `title` keeps the meaning)
 *   <768px   off-canvas drawer opened by the hamburger in the top bar
 *
 * Active state is the three-part accent treatment: soft accent background,
 * accent text and a 3px accent bar on the item's left edge.
 */
export function ClientSidebar({ open, onClose }: ClientSidebarProps) {
  const { pathname } = useLocation();

  // A drawer must never outlive the navigation that opened it.
  useEffect(() => onClose(), [pathname, onClose]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  return (
    <nav
      className={['client-nav', open ? 'is-open' : ''].filter(Boolean).join(' ')}
      aria-label="Primary"
    >
      <div className="client-nav__brand">
        <span className="client-nav__mark" aria-hidden="true" />
        <span className="client-nav__brand-text">
          <span className="client-nav__brand-name">JIIT Placement</span>
          <span className="client-nav__brand-sub">Student dashboard</span>
        </span>
        <button type="button" className="client-nav__close" onClick={onClose} aria-label="Close navigation">
          <Icon name="x" size={18} />
        </button>
      </div>

      <ul className="client-nav__list">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              title={item.label}
              className={({ isActive }) =>
                ['client-nav__item', isActive ? 'is-active' : ''].filter(Boolean).join(' ')
              }
            >
              <Icon name={item.icon} size={18} className="client-nav__icon" />
              <span className="client-nav__label">{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>

      <p className="client-nav__foot">Placement cell · session 2026–27</p>
    </nav>
  );
}
