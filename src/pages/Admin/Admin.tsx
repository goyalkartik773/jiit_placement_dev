import { useCallback, useMemo, useState } from 'react';
import { toConsoleLines } from '../../components/admin/ScriptConsole/ScriptConsole';
import { ActivityTimeline } from '../../components/admin/ActivityTimeline/ActivityTimeline';
import { AdminLogin } from '../../components/admin/AdminLogin/AdminLogin';
import { InventoryStrip } from '../../components/admin/InventoryStrip/InventoryStrip';
import { RunHistory } from '../../components/admin/RunHistory/RunHistory';
import { ScriptsPanel } from '../../components/admin/ScriptsPanel/ScriptsPanel';
import { Button } from '../../components/common/Button/Button';
import { useToast } from '../../components/common/Toast/Toast';
import { useActivity } from '../../hooks/useActivity';
import { useAdminOverview } from '../../hooks/useAdminOverview';
import { useScriptRunner } from '../../hooks/useScriptRunner';
import { adminLogout, clearAdminToken, getAdminToken, getAdminUsername } from '../../services/adminService';
import type { AdminActivityItem, AdminOverview, AdminScriptAction } from '../../types/admin.types';
import { formatDateTime, formatRelative } from '../../utils/format';
import './Admin.scss';

/** Session facts of the header strip — every value comes from the overview. */
function sessionLine(overview: AdminOverview | null, loading: boolean): string {
  const parts: string[] = [];
  const username = getAdminUsername();
  const session = overview?.session;

  if (username) parts.push(username);
  if (session?.lastLogin) {
    parts.push(`Last sign-in ${formatRelative(session.lastLogin) ?? formatDateTime(session.lastLogin)}`);
  }
  if (typeof session?.logins === 'number') {
    parts.push(`${session.logins.toLocaleString()} sign-in${session.logins === 1 ? '' : 's'}`);
  }

  if (parts.length > 0) return parts.join(' · ');
  return loading ? 'Loading session…' : 'Signed in';
}

/**
 * Admin console (container): sign-in gate, then the overview strip, the
 * unified scripts panel, the run history and the activity timeline.
 * All fetching/polling lives in useAdminOverview / useActivity /
 * useScriptRunner → adminService → apiClient; this page only wires state.
 */
export function Admin() {
  const { showToast } = useToast();
  const [token, setToken] = useState<string | null>(() => getAdminToken());
  const [replay, setReplay] = useState<AdminActivityItem | null>(null);

  // Parallel 401s must only sign out once.
  const handleUnauthorized = useCallback(() => {
    if (!getAdminToken()) return;
    clearAdminToken();
    setToken(null);
    setReplay(null);
    showToast('Your session ended. Please sign in again.', 'error');
  }, [showToast]);

  const overview = useAdminOverview(token, handleUnauthorized);
  const activity = useActivity(token, handleUnauthorized);
  const { reload: reloadOverview } = overview;
  const { reload: reloadActivity } = activity;

  // A finished run changes both the inventory numbers and the history.
  const handleSettled = useCallback(() => {
    reloadOverview();
    reloadActivity();
  }, [reloadOverview, reloadActivity]);

  const runner = useScriptRunner(token, handleUnauthorized, handleSettled);

  const handleLogin = useCallback((nextToken: string) => {
    setToken(nextToken);
    setReplay(null);
  }, []);

  const handleLogout = useCallback(async (): Promise<void> => {
    try {
      await adminLogout();
    } finally {
      setToken(null);
      setReplay(null);
      showToast('Signed out.', 'success');
    }
  }, [showToast]);

  const handleRun = useCallback((action: AdminScriptAction) => {
    setReplay(null);
    runner.start(action);
  }, [runner]);

  const handleRefresh = useCallback(() => {
    reloadOverview();
    reloadActivity();
  }, [reloadOverview, reloadActivity]);

  // The console shows the archived rows while replaying, the live merged log otherwise.
  const consoleLines = useMemo(
    () => (replay ? toConsoleLines(replay.output) : runner.lines),
    [replay, runner.lines],
  );

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
            {sessionLine(overview.overview, overview.initialLoading)}
          </p>
        </div>
        <div className="admin-page__actions">
          <Button variant="ghost" size="sm" icon="refresh" loading={overview.refreshing} onClick={handleRefresh}>
            Refresh
          </Button>
          <Button variant="ghost" size="sm" icon="logout" onClick={() => void handleLogout()}>
            Log out
          </Button>
        </div>
      </section>

      <InventoryStrip
        overview={overview.overview}
        loading={overview.initialLoading}
        error={overview.error}
        onRetry={reloadOverview}
      />

      <div className="admin-page__grid">
        <ScriptsPanel
          action={runner.action}
          status={runner.status}
          busy={runner.busy}
          starting={runner.starting}
          pendingAction={runner.pendingAction}
          conflict={runner.conflict}
          conflictScript={runner.conflictScript}
          error={runner.error}
          lines={consoleLines}
          replay={replay}
          onRun={handleRun}
          onDismissReplay={() => setReplay(null)}
        />

        <RunHistory
          items={activity.items}
          totalCount={activity.totalCount}
          loading={activity.loading}
          loadingMore={activity.loadingMore}
          error={activity.error}
          hasMore={activity.hasMore}
          activeId={replay?.id ?? null}
          onReplay={setReplay}
          onLoadMore={activity.loadMore}
          onRetry={reloadActivity}
        />
      </div>

      <ActivityTimeline
        items={activity.items}
        totalCount={activity.totalCount}
        loading={activity.loading}
        error={activity.error}
        activeId={replay?.id ?? null}
        onReplay={setReplay}
        onRetry={reloadActivity}
      />
    </div>
  );
}
