import type { ReactNode } from 'react';
import { Badge, type BadgeTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { ErrorState } from '../../common/ErrorState/ErrorState';
import { Icon, type IconName } from '../../common/Icon/Icon';
import { Panel } from '../../common/Panel/Panel';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import type { AdminSyncState, AdminSyncStatus } from '../../../types/admin.types';
import './SyncPanel.scss';

interface SyncPanelProps {
  count: number | null;
  countLoading: boolean;
  countError: string | null;
  status: AdminSyncStatus | null;
  statusLoading: boolean;
  statusError: string | null;
  starting: boolean;
  startError: string | null;
  onStart: () => void;
  /** Reload count + status — also the retry action for every load error. */
  onRefresh: () => void;
}

const PILL: Record<AdminSyncState, { tone: BadgeTone; label: string }> = {
  idle: { tone: 'neutral', label: 'Idle' },
  running: { tone: 'info', label: 'Running' },
  completed: { tone: 'success', label: 'Completed' },
  failed: { tone: 'danger', label: 'Failed' },
};

const PANEL_ICON: Record<AdminSyncState, IconName> = {
  idle: 'refresh',
  running: 'refresh',
  completed: 'check-circle',
  failed: 'alert-circle',
};

/** Numbers are server-owned; unknown values render an em dash, never a guess. */
function formatValue(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toLocaleString() : '—';
}

interface StatItemProps {
  icon: IconName;
  label: string;
  value: number | null | undefined;
  tone?: 'default' | 'danger';
}

function StatItem({ icon, label, value, tone = 'default' }: StatItemProps) {
  const showDanger = tone === 'danger' && typeof value === 'number' && value > 0;

  return (
    <div className="sync-stats__item">
      <dt className="sync-stats__label">
        <Icon name={icon} size={14} />
        {label}
      </dt>
      <dd className={`sync-stats__value${showDanger ? ' sync-stats__value--danger' : ''}`}>{formatValue(value)}</dd>
    </div>
  );
}

/**
 * The one card of the admin console: database count + sync lifecycle
 * (idle → running progress → completed result / failure), driven entirely
 * by the status endpoint.
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
  onStart,
  onRefresh,
}: SyncPanelProps) {
  const state: AdminSyncState = status?.status ?? 'idle';
  const pill = PILL[state];
  const totalFailure = statusError !== null && status === null;
  const progress = status?.progress;
  const jobsTotal = status?.jobsTotal;
  const jobsProcessed = status?.jobsProcessed;

  // The count row always carries the shared Refresh/reload control, so the
  // state actions only need the primary start/again/fail action.
  const actions = (
    <div className="sync-panel__actions">
      <Button variant="primary" icon="zap" onClick={onStart} loading={starting}>
        {state === 'completed' ? 'Sync again' : state === 'failed' ? 'Try again' : 'Sync New Jobs'}
      </Button>
    </div>
  );

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

  function renderBody(): ReactNode {
    if (statusLoading) {
      return (
        <div className="sync-panel__loading" aria-hidden="true">
          <Skeleton width="full" height="md" shape="pill" />
          <Skeleton width="lg" height="sm" shape="pill" />
        </div>
      );
    }

    if (totalFailure) {
      return <ErrorState title="Could not load sync status" message={statusError} onRetry={onRefresh} />;
    }

    if (state === 'running' && status) {
      return (
        <div className="sync-panel__running">
          <div className="sync-panel__progress-head">
            <span className="sync-panel__progress-label">
              {typeof jobsTotal === 'number'
                ? `${formatValue(jobsProcessed)} of ${formatValue(jobsTotal)} jobs processed`
                : 'Fetching the job list from SuperSet…'}
            </span>
            {typeof progress === 'number' ? <span className="sync-panel__progress-pct">{progress}%</span> : null}
          </div>

          {/* Native progress = accessible value (or indeterminate) with zero inline styles. */}
          {typeof progress === 'number' ? (
            <progress className="sync-panel__progress" max={100} value={progress} aria-label="Synchronization progress" />
          ) : (
            <progress className="sync-panel__progress sync-panel__progress--indeterminate" aria-label="Synchronization progress" />
          )}

          <dl className="sync-stats">
            <StatItem icon="briefcase" label="Jobs before" value={status.totalJobsBeforeSync} />
            <StatItem icon="zap" label="New jobs" value={status.newJobs} />
            <StatItem icon="paperclip" label="Documents" value={status.documentsDownloaded} />
            <StatItem icon="alert-circle" label="Failed jobs" value={status.failedJobs} tone="danger" />
          </dl>

          <p className="sync-panel__note">Runs on the server — you can leave this page while it continues.</p>
        </div>
      );
    }

    if (state === 'completed' && status) {
      return (
        <div className="sync-panel__result sync-panel__result--success">
          <div className="sync-panel__result-head">
            <span className="sync-panel__result-icon" aria-hidden="true">
              <Icon name="check-circle" size={18} />
            </span>
            <div className="sync-panel__result-text">
              <p className="sync-panel__result-title">Synchronization complete</p>
              {status.message ? <p className="sync-panel__result-sub">{status.message}</p> : null}
            </div>
          </div>

          <p className="sync-panel__flow">
            <span className="sync-panel__flow-num">{formatValue(status.totalJobsBeforeSync)}</span>
            <Icon name="chevron-right" size={16} className="sync-panel__flow-arrow" />
            <span className="sync-panel__flow-num sync-panel__flow-num--after">{formatValue(status.totalJobsAfterSync)}</span>
            <span className="sync-panel__flow-unit">jobs in database</span>
          </p>

          <dl className="sync-stats">
            <StatItem icon="zap" label="New jobs" value={status.newJobs} />
            <StatItem icon="paperclip" label="Documents" value={status.documentsDownloaded} />
            <StatItem icon="file" label="Docs failed" value={status.documentsFailed} tone="danger" />
            <StatItem icon="alert-circle" label="Failed jobs" value={status.failedJobs} tone="danger" />
          </dl>

          {actions}
        </div>
      );
    }

    if (state === 'failed' && status) {
      return (
        <div className="sync-panel__result sync-panel__result--danger" role="alert">
          <div className="sync-panel__result-head">
            <span className="sync-panel__result-icon" aria-hidden="true">
              <Icon name="alert-circle" size={18} />
            </span>
            <div className="sync-panel__result-text">
              <p className="sync-panel__result-title">Synchronization failed</p>
              <p className="sync-panel__result-sub">{status.error ?? status.message ?? 'No error detail was reported.'}</p>
            </div>
          </div>
          {actions}
        </div>
      );
    }

    // idle
    return (
      <div className="sync-panel__idle">
        <p className="sync-panel__hint">
          Pulls the latest listings and documents from SuperSet into the database. One sync runs at a time and existing
          documents are kept.
        </p>
        {actions}
      </div>
    );
  }

  return (
    <Panel
      className="sync-panel"
      icon={PANEL_ICON[state]}
      title="Job synchronization"
      meta={
        statusLoading ? (
          <Skeleton width="sm" height="xs" shape="pill" />
        ) : (
          <Badge tone={pill.tone} dot={state === 'running'}>
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
          otherwise the status ErrorState already explains the outage. */}
      {countError && status ? errorRow(countError) : null}

      {renderBody()}

      {/* A failed refresh keeps the last known status on screen — flag it. */}
      {statusError && status ? errorRow(statusError) : null}

      {startError ? errorRow(startError) : null}
    </Panel>
  );
}
