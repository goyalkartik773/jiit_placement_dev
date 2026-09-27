import { Link, useLocation } from 'react-router-dom';
import { API_BASE_URL } from '../../../services/apiClient';
import './Header.scss';

function apiHostLabel(): string {
  try {
    return new URL(API_BASE_URL).host;
  } catch {
    return API_BASE_URL;
  }
}

interface NavSection {
  to: string;
  label: string;
  /** True when the current pathname belongs to this section. */
  isActive: (pathname: string) => boolean;
}

/** The four dashboard sections, in navigation order. */
const SECTIONS: NavSection[] = [
  { to: '/', label: 'Active Job Listing', isActive: (path) => path === '/' || path.startsWith('/jobs/') },
  { to: '/placements', label: 'Company-Wise Placement', isActive: (path) => path === '/placements' },
  { to: '/email-notices', label: 'Email Notices', isActive: (path) => path === '/email-notices' },
  { to: '/superset-notices', label: 'Superset Notices', isActive: (path) => path === '/superset-notices' },
];

/** Breadcrumb-style context label — derived from the current route. */
function contextLabel(pathname: string): string {
  if (pathname === '/') return 'Active Job Listing';
  if (pathname.startsWith('/jobs/')) return 'Job Details';
  if (pathname === '/placements') return 'Company-Wise Placement';
  if (pathname === '/email-notices') return 'Email Notices';
  if (pathname === '/superset-notices') return 'Superset Notices';
  if (pathname === '/admin') return 'Admin Console';
  return 'Page Not Found';
}

export function Header() {
  const { pathname } = useLocation();

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-header__brand">
          <Link to="/" className="brand" aria-label="JIIT Placement — go to jobs">
            <span className="brand__mark" aria-hidden="true" />
            <span className="brand__name">JIIT Placement</span>
          </Link>
          <span className="app-header__sep" aria-hidden="true">
            /
          </span>
          <Link to="/" className="app-header__context" title="Back to the job listing">
            {contextLabel(pathname)}
          </Link>
        </div>

        <div className="app-header__tools">
          <Link
            to="/admin"
            className="app-header__admin"
            aria-current={pathname === '/admin' ? 'page' : undefined}
            title="Admin sync console"
          >
            Admin
          </Link>
          <span className="api-status" title={`Backend API base URL — ${API_BASE_URL}`}>
            <span className="api-status__dot" aria-hidden="true" />
            api · {apiHostLabel()}
          </span>
        </div>
      </div>

      <nav className="app-header__nav" aria-label="Dashboard sections">
        <ul className="app-header__nav-list">
          {SECTIONS.map((section) => (
            <li key={section.to} className="app-header__nav-item">
              <Link
                to={section.to}
                className="app-header__nav-link"
                aria-current={section.isActive(pathname) ? 'page' : undefined}
              >
                {section.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
