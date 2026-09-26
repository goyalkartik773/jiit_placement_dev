import { useCallback, useState } from 'react';
import { AdminLogin } from '../../components/admin/AdminLogin/AdminLogin';
import { SyncPanel } from '../../components/admin/SyncPanel/SyncPanel';
import { Button } from '../../components/common/Button/Button';
import { useToast } from '../../components/common/Toast/Toast';
import { useAdminSync } from '../../hooks/useAdminSync';
import { adminLogout, clearAdminToken, getAdminToken } from '../../services/adminService';
import './Admin.scss';

function countLine(count: number | null, loading: boolean): string {
  if (count !== null) return `${count.toLocaleString()} ${count === 1 ? 'job' : 'jobs'} in the database`;
  return loading ? 'Loading job count…' : 'Job count unavailable';
}

/**
 * Admin console (container).
 * Auth state decides between the sign-in form and the sync console;
 * all fetching/polling lives in useAdminSync → adminService → apiClient.
 */
export function Admin() {
  const { showToast } = useToast();
  const [token, setToken] = useState<string | null>(() => getAdminToken());

  // Parallel 401s must only sign out once.
  const handleUnauthorized = useCallback(() => {
    if (!getAdminToken()) return;
    clearAdminToken();
    setToken(null);
    showToast('Your session ended. Please sign in again.', 'error');
  }, [showToast]);

  const sync = useAdminSync(token, handleUnauthorized);

  const handleLogin = useCallback((nextToken: string) => {
    setToken(nextToken);
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      await adminLogout();
    } finally {
      setToken(null);
      showToast('Signed out.', 'success');
    }
  }, [showToast]);

  if (!token) {
    return (
      <div className="page admin-page">
        <AdminLogin onLogin={handleLogin} />
      </div>
    );
  }

  return (
    <div className="page admin-page">
      <section className="page-head">
        <div className="page-head__text">
          <p className="page-head__eyebrow">Admin · Restricted</p>
          <h1 className="page-head__title">Admin console</h1>
          <p className="page-head__count" aria-live="polite">
            {countLine(sync.count, sync.countLoading)}
          </p>
        </div>
        <div className="admin-page__actions">
          <Button variant="ghost" size="sm" icon="logout" onClick={() => void handleLogout()}>
            Log out
          </Button>
        </div>
      </section>

      <SyncPanel
        count={sync.count}
        countLoading={sync.countLoading}
        countError={sync.countError}
        status={sync.status}
        statusLoading={sync.statusLoading}
        statusError={sync.statusError}
        starting={sync.starting}
        startError={sync.startError}
        deleting={sync.deleting}
        lines={sync.lines}
        busy={sync.busy}
        onStart={sync.start}
        onDelete={sync.remove}
        onRefresh={sync.reload}
      />
    </div>
  );
}
