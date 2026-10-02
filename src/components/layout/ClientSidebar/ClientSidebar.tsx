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

interface NavGroup {
  label: string;
  items: NavItem[];
}

/**
 * Client navigation, in product order, grouped by what the reader is doing
 * with it: reading the market (Overview), acting on openings (Opportunities),
 * reacting to what landed in the mailbox (Alerts).
 *
 * The groups are presentational — every route, label and icon is unchanged,
 * and each group owns a labelled nested list so assistive tech announces
 * "Alerts, list, 2 items" before the item itself.
 */
const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [
      { to: '/', label: 'Dashboard', icon: 'home', end: true },
      { to: '/analytics', label: 'Analytics', icon: 'chart', end: true },
    ],
  },
  {
    label: 'Opportunities',
    items: [
      { to: '/jobs', label: 'Active Job Listing', icon: 'briefcase' },
      { to: '/placements', label: 'Company-Wise Placement', icon: 'building' },
    ],
  },
  {
    label: 'Alerts',
    items: [
      { to: '/email-notices', label: 'Email Notices', icon: 'inbox' },
      { to: '/superset-notices', label: 'Superset Notices', icon: 'bell' },
    ],
  },
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
 *   ≥1024px  full rail — product mark, labelled groups
 *   768–1023 icon-only rail (labels collapse, `title` keeps the meaning)
 *   <768px   off-canvas drawer opened by the hamburger in the bar
 *
 * Active state is the accent treatment: soft accent background, accent text
 * and a 3px accent bar on the item's left edge. `NavLink` also writes
 * `aria-current="page"`, so the state is never colour-only.
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
        <span className="client-nav__mark" aria-hidden="true">
          J
        </span>
        <span className="client-nav__brand-text">
          <span className="client-nav__brand-name">JIIT Placement</span>
          <span className="client-nav__brand-sub">Student dashboard</span>
        </span>
        <button type="button" className="client-nav__close" onClick={onClose} aria-label="Close navigation">
          <Icon name="x" size={18} />
        </button>
      </div>

      <div className="client-nav__groups">
        {NAV_GROUPS.map((group) => {
          const labelId = `nav-group-${group.label.toLowerCase().replace(/\s+/g, '-')}`;
          return (
            <div className="client-nav__group" key={group.label}>
              <p className="client-nav__group-label" id={labelId}>
                {group.label}
              </p>
              <ul className="client-nav__list" aria-labelledby={labelId}>
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      title={item.label}
                      className={({ isActive }) =>
                        ['client-nav__item', isActive ? 'is-active' : ''].filter(Boolean).join(' ')
                      }
                    >
                      <Icon name={item.icon} size={17} className="client-nav__icon" />
                      <span className="client-nav__label">{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <p className="client-nav__foot">Placement cell · session 2026–27</p>
    </nav>
  );
}
