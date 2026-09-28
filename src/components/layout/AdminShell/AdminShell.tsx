import { Outlet } from 'react-router-dom';
import { API_BASE_URL } from '../../../services/apiClient';
import './AdminShell.scss';

function apiHostLabel(): string {
  try {
    return new URL(API_BASE_URL).host;
  } catch {
    return API_BASE_URL;
  }
}

interface AdminNavItem {
  href: string;
  label: string;
}

/**
 * Admin-only navigation. Every entry is a section of the console page — there
 * is nowhere else for an administrator to go, and no client route is exposed
 * here (the client shell never links back to `/admin` either).
 */
const ADMIN_NAV: AdminNavItem[] = [
  { href: '#inventory', label: 'Inventory' },
  { href: '#scripts', label: 'Scripts' },
  { href: '#history', label: 'Run history' },
  { href: '#activity', label: 'Activity' },
];

/**
 * Admin shell — deliberately its own thing.
 *
 * Technical/console language: monospace type, a dark chrome bar, uppercase
 * labels and a live API-host readout. It shares no component, colour or
 * typographic voice with the client shell, and it carries no friendly
 * dashboard navigation — an administrator gets the console and nothing else.
 */
export function AdminShell() {
  return (
    <div className="admin-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      <header className="admin-shell__bar">
        <div className="admin-shell__brand">
          <span className="admin-shell__mark" aria-hidden="true" />
          <span className="admin-shell__brand-name">JIIT Placement</span>
          <span className="admin-shell__slash" aria-hidden="true">
            /
          </span>
          <span className="admin-shell__console">admin console</span>
        </div>

        <nav className="admin-shell__nav" aria-label="Admin console sections">
          {ADMIN_NAV.map((item) => (
            <a key={item.href} className="admin-shell__nav-link" href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <span className="admin-shell__api" title={`Backend API base URL — ${API_BASE_URL}`}>
          <span className="admin-shell__api-dot" aria-hidden="true" />
          api · {apiHostLabel()}
        </span>
      </header>

      <main id="main-content" className="admin-shell__main">
        <Outlet />
      </main>
    </div>
  );
}
