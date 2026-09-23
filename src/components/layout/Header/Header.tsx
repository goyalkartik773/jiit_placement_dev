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

/** Breadcrumb-style context label — derived from the current route. */
function contextLabel(pathname: string): string {
  if (pathname === '/') return 'Active Job Listing';
  if (pathname.startsWith('/jobs/')) return 'Job Details';
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

        <span className="api-status" title={`Backend API base URL — ${API_BASE_URL}`}>
          <span className="api-status__dot" aria-hidden="true" />
          API {apiHostLabel()}
        </span>
      </div>
    </header>
  );
}
