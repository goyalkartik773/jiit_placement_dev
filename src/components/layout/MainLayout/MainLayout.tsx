import { useCallback, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Icon } from '../../common/Icon/Icon';
import { Footer } from '../Footer/Footer';
import { ClientSidebar } from '../ClientSidebar/ClientSidebar';
import './MainLayout.scss';

/** Section name for the slim top bar — derived from the current route. */
function contextLabel(pathname: string): string {
  if (pathname === '/') return 'Dashboard';
  if (pathname === '/analytics') return 'Analytics';
  if (pathname.startsWith('/jobs/')) return 'Job Details';
  if (pathname.startsWith('/jobs')) return 'Active Job Listing';
  if (pathname === '/placements') return 'Company-Wise Placement';
  if (pathname === '/email-notices') return 'Email Notices';
  if (pathname === '/superset-notices') return 'Superset Notices';
  return 'Page Not Found';
}

/**
 * Client shell: left navigation rail + content column to its right.
 *
 * This shell is student-facing only — no admin link, no sync/script controls,
 * no API-host chip and no "ADMIN" badge. The admin console lives in its own
 * separate shell (`AdminShell`) with its own chrome.
 *
 * The rail is a full sidebar ≥860px, icon-only below that, and an off-canvas
 * drawer below 640px opened by the hamburger in the top bar.
 */
export function MainLayout() {
  const { pathname } = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  return (
    <div className="client-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      <ClientSidebar open={drawerOpen} onClose={closeDrawer} />
      {drawerOpen ? (
        <button type="button" className="client-shell__scrim" aria-label="Close navigation" onClick={closeDrawer} />
      ) : null}

      <div className="client-shell__body">
        <div className="client-shell__bar">
          <button
            type="button"
            className="client-shell__menu"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <Icon name="menu" size={20} />
          </button>
          <span className="client-shell__title">{contextLabel(pathname)}</span>
        </div>

        <main id="main-content" className="app-main">
          <Outlet />
        </main>

        <Footer />
      </div>
    </div>
  );
}
