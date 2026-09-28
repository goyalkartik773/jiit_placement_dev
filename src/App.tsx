import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ToastProvider } from './components/common/Toast/Toast';
import { AdminShell } from './components/layout/AdminShell/AdminShell';
import { MainLayout } from './components/layout/MainLayout/MainLayout';
import { Admin } from './pages/Admin/Admin';
import { Dashboard } from './pages/Dashboard/Dashboard';
import { EmailNotices } from './pages/EmailNotices/EmailNotices';
import { JobDetails } from './pages/JobDetails/JobDetails';
import { Jobs } from './pages/Jobs/Jobs';
import { NotFound } from './pages/NotFound/NotFound';
import { Placements } from './pages/Placements/Placements';
import { SupersetNotices } from './pages/SupersetNotices/SupersetNotices';

/**
 * Route table — two separate shells, never one merged navigation:
 *
 *   admin shell (AdminShell — own chrome, admin-only nav)
 *     /admin            -> Admin console (sign-in + job sync)
 *
 *   client shell (MainLayout — left rail, student-facing)
 *     /                 -> Dashboard (client home)
 *     /jobs             -> Active Job Listing
 *     /placements       -> Company-wise placement summary
 *     /email-notices    -> Notices parsed from the placement emails
 *     /superset-notices -> Notices synced from the Superset portal
 *     /jobs/:jobId      -> Job details
 *     *                 -> NotFound
 *
 * An unmatched /admin/* path falls through to the client catch-all rather
 * than exposing the console chrome to a route that does not exist.
 */
export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/admin" element={<Admin />} />
          </Route>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/jobs/:jobId" element={<JobDetails />} />
            <Route path="/placements" element={<Placements />} />
            <Route path="/email-notices" element={<EmailNotices />} />
            <Route path="/superset-notices" element={<SupersetNotices />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
