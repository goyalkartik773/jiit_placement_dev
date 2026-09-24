import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout/MainLayout';
import { ToastProvider } from './components/common/Toast/Toast';
import { Admin } from './pages/Admin/Admin';
import { JobDetails } from './pages/JobDetails/JobDetails';
import { Jobs } from './pages/Jobs/Jobs';
import { NotFound } from './pages/NotFound/NotFound';

/**
 * Route table:
 *   /                 -> Jobs listing
 *   /jobs/:jobId      -> Job details
 *   /admin            -> Admin console (sign-in + job sync)
 *   *                 -> NotFound
 * Wrapped in the app shell (MainLayout) and the global ToastProvider.
 */
export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Jobs />} />
            <Route path="/jobs/:jobId" element={<JobDetails />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
