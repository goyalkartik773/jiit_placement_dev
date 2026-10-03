import { useCallback, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { BrandMark } from '../../common/BrandMark/BrandMark';
import { Icon } from '../../common/Icon/Icon';
import { Footer } from '../Footer/Footer';
import { ClientSidebar } from '../ClientSidebar/ClientSidebar';
import './MainLayout.scss';

/**
 * Client shell: left navigation rail + content column to its right.
 *
 * This shell is student-facing only — no admin link, no sync/script controls,
 * no API-host chip and no "ADMIN" badge. The admin console lives in its own
 * separate shell (`AdminShell`) with its own chrome.
 *
 * The rail is a full sidebar ≥860px, icon-only below that, and an off-canvas
 * drawer below 640px opened by the hamburger in the bar.
 *
 * There is deliberately NO section title in the bar any more. Every route
 * already states where you are — `PageHeader` / `page-head` print the `<h1>`
 * and its eyebrow, `JobHeader` carries its own "All Jobs" breadcrumb over a
 * company `<h1>`, and `NotFoundState` says "Page not found" — so the bar was
 * printing "Company-Wise Placement" directly above a heading that read
 * "Company-wise placement". Below 640px the rail is gone entirely, so the bar
 * reappears there carrying the menu button and the product mark instead: the
 * one thing the hidden drawer would otherwise take with it.
 */
export function MainLayout() {
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

          <span className="client-shell__brand">
            <BrandMark size="md" />
            <span className="client-shell__brand-name">JIIT Placement</span>
          </span>
        </div>

        <main id="main-content" className="app-main">
          <Outlet />
        </main>

        <Footer />
      </div>
    </div>
  );
}
