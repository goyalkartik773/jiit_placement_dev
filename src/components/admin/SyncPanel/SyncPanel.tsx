import { useEffect, useState, type ReactNode } from 'react';
import { Badge, type BadgeTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
import { Panel } from '../../common/Panel/Panel';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import { ScriptConsole, type ConsoleLine } from '../ScriptConsole/ScriptConsole';
import type { AdminSyncState, AdminSyncStatus } from '../../../types/admin.types';
import './SyncPanel.scss';

/** How long the destructive button waits for the confirming second click. */
const ARM_MS = 4000;

interface SyncPanelProps {
  count: number | null;
  countLoading: boolean;
  countError: string | null;
  status: AdminSyncStatus | null;
  statusLoading: boolean;
  statusError: string | null;
  starting: boolean;
  startError: string | null;
  deleting: boolean;
  /** Console output from the hook (real server responses only). */
  lines: ConsoleLine[];
  /** True while a sync or delete runs — drives the console cursor. */
  busy: boolean;
  onStart: () => void;
  onDelete: () => void;
  /** Reload count + status — also the retry action for every load error. */
  onRefresh: () => void;
}

const PILL: Record<AdminSyncState, { tone: BadgeTone; label: string }> = {
  idle: { tone: 'neutral', label: 'Idle' },
  running: { tone: 'info', label: 'Running' },
  completed: { tone: 'success', label: 'Completed' },
  failed: { tone: 'danger', label: 'Failed' },
};

/** Numbers are server-owned; unknown values render an em dash, never a guess. */
function formatValue(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toLocaleString() : '—';
}

/**
 * The admin operations card: database count, the two script actions
 * (sync / delete-all with a confirm step) and the terminal-style console
 * that prints every real server response.
 */
export function SyncPanel({
  count,
  countLoading,
  countError,
  status,
  statusLoading,
  statusError,
  starting,
  startError,
  deleting,
  lines,
  busy,
  onStart,
  onDelete,
  onRefresh,
}: SyncPanelProps) {
  const state: AdminSyncState = status?.status ?? 'idle';
  const pill = PILL[state];
  const running = state === 'running';

  // Destructive action: first click arms, second click inside ARM_MS executes.
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = window.setTimeout(() => setArmed(false), ARM_MS);
    return () => window.clearTimeout(timer);
  }, [armed]);

  function handleDeleteClick(): void {
    if (!armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    onDelete();
  }

  function errorRow(message: string): ReactNode {
    return (
      <p className="sync-panel__error" role="alert">
        <Icon name="alert-circle" size={15} />
        <span className="sync-panel__error-text">{message}</span>
        <Button variant="soft" size="sm" onClick={onRefresh}>
          Retry
        </Button>
      </p>
    );
  }

  return (
    <Panel
      className="sync-panel"
      icon="terminal"
      title="Sync & cleanup"
      meta={
        statusLoading ? (
          <Skeleton width="sm" height="xs" shape="pill" />
        ) : (
          <Badge tone={pill.tone} dot={running}>
            {pill.label}
          </Badge>
        )
      }
    >
      <div className="sync-panel__count">
        <span className="sync-panel__count-main">
          <span className="sync-panel__count-label">Jobs in database</span>
          <span className="sync-panel__count-value" aria-live="polite">
            {countLoading ? <Skeleton width="md" height="lg" /> : formatValue(count)}
          </span>
        </span>
        <Button variant="ghost" size="sm" icon="refresh" onClick={onRefresh} loading={countLoading}>
          Refresh
        </Button>
      </div>

      {/* Count failure is only surfaced once the status view is usable —
          otherwise the status row already explains the outage. */}
      {countError && status ? errorRow(countError) : null}

      <div className="sync-panel__actions">
        <Button
          variant="primary"
          icon="zap"
          onClick={onStart}
          loading={starting}
          disabled={deleting || running}
          title={running ? 'A synchronization is already running' : undefined}
        >
          {state === 'completed' ? 'Sync again' : state === 'failed' ? 'Try again' : 'Sync New Jobs'}
        </Button>

        <Button
          variant="danger"
          icon="trash"
          onClick={handleDeleteClick}
          loading={deleting}
          disabled={starting || running}
          title={armed ? 'Click again to confirm the deletion' : 'Deletes every job and its documents'}
        >
          {armed ? 'Click again to confirm' : 'Delete all jobs'}
        </Button>

        {armed ? (
          <span className="sync-panel__armed" role="status">
            Removes all {formatValue(count)} jobs and their documents from the database and disk.
          </span>
        ) : null}
      </div>

      {/* Native progress = accessible value (or indeterminate) with zero inline styles. */}
      {running && status ? (
        <div className="sync-panel__progress-row">
          <div className="sync-panel__progress-head">
            <span className="sync-panel__progress-label">
              {typeof status.jobsTotal === 'number'
                ? `${formatValue(status.jobsProcessed)} of ${formatValue(status.jobsTotal)} jobs processed`
                : 'Fetching the job list from SuperSet…'}
            </span>
            {typeof status.progress === 'number' ? (
              <span className="sync-panel__progress-pct">{status.progress}%</span>
            ) : null}
          </div>

          {typeof status.progress === 'number' ? (
            <progress className="sync-panel__progress" max={100} value={status.progress} aria-label="Synchronization progress" />
          ) : (
            <progress className="sync-panel__progress sync-panel__progress--indeterminate" aria-label="Synchronization progress" />
          )}
        </div>
      ) : null}

      <ScriptConsole lines={lines} busy={busy} title="admin@jiit-placement:~/jobs" />

      {/* A failed refresh keeps the last known status on screen — flag it. */}
      {statusError && status ? errorRow(statusError) : null}

      {startError ? errorRow(startError) : null}
    </Panel>
  );
}
