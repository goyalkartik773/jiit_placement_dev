import { useCallback, useEffect, useRef, useState } from 'react';
import { useToast } from '../components/common/Toast/Toast';
import type { ConsoleLine, ConsoleTone } from '../components/admin/ScriptConsole/ScriptConsole';
import { API_BASE_URL, ApiError, isAbortError } from '../services/apiClient';
import { deleteAllJobs, fetchAdminJobCount, fetchSyncStatus, startJobSync } from '../services/adminService';
import type { AdminSyncStatus } from '../types/admin.types';

/** Server-side syncs take minutes; 2s keeps the progress honest without hammering the API. */
const STATUS_POLL_MS = 2000;

/** The console keeps the most recent output only (a full sync is well under this). */
const MAX_LOG_LINES = 200;

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'The request could not be completed.';
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.httpStatus === 401;
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

function completionToast(status: AdminSyncStatus): string {
  const jobs = status.newJobs ?? 0;
  const docs = status.documentsDownloaded ?? 0;
  return `Sync completed — ${plural(jobs, 'new job')}, ${plural(docs, 'document')} downloaded.`;
}

function formatCount(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toLocaleString() : '?';
}

/** One progress row from the server's real counters — bar included, nothing estimated. */
function progressLine(status: AdminSyncStatus): string {
  const processed = status.jobsProcessed ?? 0;
  const total = status.jobsTotal ?? processed;
  const parts = [`${formatCount(processed)}/${formatCount(total)} processed`];
  if (typeof status.newJobs === 'number') parts.push(`${status.newJobs} new`);
  if (typeof status.documentsDownloaded === 'number') parts.push(`${status.documentsDownloaded} docs`);
  if (typeof status.failedJobs === 'number' && status.failedJobs > 0) parts.push(`${status.failedJobs} failed`);

  const pct = typeof status.progress === 'number' ? status.progress : null;
  if (pct === null) return `  ${parts.join(' · ')}`;

  const filled = Math.max(0, Math.min(10, Math.round(pct / 10)));
  return `  [${'█'.repeat(filled)}${'░'.repeat(10 - filled)}] ${pct}% — ${parts.join(' · ')}`;
}

/** Final summary line built from the completed run's counters. */
function completionLine(status: AdminSyncStatus): string {
  const before = status.totalJobsBeforeSync;
  const after = status.totalJobsAfterSync;
  const flow =
    typeof before === 'number' && typeof after === 'number'
      ? `${formatCount(before)} → ${formatCount(after)} jobs`
      : `${formatCount(after)} jobs in database`;
  return `  ${flow} · ${status.newJobs ?? 0} new · ${status.documentsDownloaded ?? 0} documents (${status.documentsFailed ?? 0} failed) · ${status.failedJobs ?? 0} failed jobs`;
}

export interface AdminSyncController {
  count: number | null;
  countLoading: boolean;
  countError: string | null;
  status: AdminSyncStatus | null;
  statusLoading: boolean;
  statusError: string | null;
  starting: boolean;
  startError: string | null;
  deleting: boolean;
  /** Console output produced from real server responses, oldest first. */
  lines: ConsoleLine[];
  /** True while a sync or delete is in flight (drives the console cursor). */
  busy: boolean;
  /** Re-fetch count + status (also the retry path for every load error). */
  reload: () => void;
  /** Start a sync. A 409 ("already running") simply adopts the live status. */
  start: () => void;
  /** Delete every job and its documents. A 409 refreshes the live state. */
  remove: () => void;
}

/**
 * Drives the admin console:
 *  - loads the job count and sync status together (parallel, abortable),
 *  - starts a sync and then polls the status endpoint while it runs,
 *  - appends terminal-style lines for every real server response
 *    (start, milestones, completion, deletion phases, failures),
 *  - fires a toast + reloads the count when a run completes,
 *  - reports 401s upward so the session can be dropped.
 * All progress values come from the server — nothing is estimated here.
 */
export function useAdminSync(token: string | null, onUnauthorized: () => void): AdminSyncController {
  const { showToast } = useToast();

  const [count, setCount] = useState<number | null>(null);
  const [countLoading, setCountLoading] = useState(false);
  const [countError, setCountError] = useState<string | null>(null);

  const [status, setStatus] = useState<AdminSyncStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const [deleting, setDeleting] = useState(false);
  const [lines, setLines] = useState<ConsoleLine[]>([]);

  const [reloadToken, setReloadToken] = useState(0);
  const [pollTick, setPollTick] = useState(0);

  // Always call the freshest callback (it closes over the current token).
  const onUnauthorizedRef = useRef(onUnauthorized);
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
  }, [onUnauthorized]);

  // ---- Console bookkeeping ----
  const lineIdRef = useRef(0);
  const bootedRef = useRef(false);
  const expiredRef = useRef(false);
  const prevStatusRef = useRef<AdminSyncStatus | null>(null);
  // Each run's milestones are emitted exactly once.
  const runRef = useRef({ syncId: null as string | null, fetching: false, listFetched: false, lastProcessed: null as number | null });

  const pushLine = useCallback((tone: ConsoleTone, text: string): void => {
    const id = lineIdRef.current++;
    const time = new Date().toLocaleTimeString('en-GB', { hour12: false });
    setLines((prev) => {
      const next = [...prev, { id, time, tone, text }];
      return next.length > MAX_LOG_LINES ? next.slice(next.length - MAX_LOG_LINES) : next;
    });
  }, []);

  const reportUnauthorized = useCallback((): void => {
    // Parallel 401s must produce a single session-expired line.
    if (!expiredRef.current) {
      expiredRef.current = true;
      pushLine('error', '✗ 401 Unauthorized — your session ended');
    }
    onUnauthorizedRef.current();
  }, [pushLine]);

  const failWith = useCallback(
    (error: unknown, setError: (message: string | null) => void): void => {
      if (isAbortError(error)) return;
      if (isUnauthorized(error)) {
        reportUnauthorized();
        return;
      }
      const message = messageOf(error);
      setError(message);
      pushLine('error', `✗ ${message}`);
    },
    [pushLine, reportUnauthorized],
  );

  // ---- Console reset on sign-out ----
  useEffect(() => {
    if (token) return;
    setLines([]);
    lineIdRef.current = 0;
    bootedRef.current = false;
    expiredRef.current = false;
    prevStatusRef.current = null;
    runRef.current = { syncId: null, fetching: false, listFetched: false, lastProcessed: null };
  }, [token]);

  // ---- Boot banner on sign-in ----
  useEffect(() => {
    if (!token || bootedRef.current) return;
    bootedRef.current = true;
    pushLine('dim', `▸ attached to ${API_BASE_URL}`);
    pushLine('dim', '→ loading job count and sync status');
    pushLine('dim', '  commands: "Sync New Jobs" pulls SuperSet listings · "Delete all jobs" removes every job + its documents');
  }, [token, pushLine]);

  // ---- Initial load / manual reload (count + status in parallel) ----
  useEffect(() => {
    if (!token) {
      setCount(null);
      setStatus(null);
      setCountError(null);
      setStatusError(null);
      setCountLoading(false);
      setStatusLoading(false);
      return;
    }

    const controller = new AbortController();
    setCountLoading(true);
    setCountError(null);
    setStatusLoading(true);
    setStatusError(null);

    fetchAdminJobCount(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setCount(value);
        setCountLoading(false);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setCountLoading(false);
        failWith(error, setCountError);
      });

    fetchSyncStatus(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setStatus(value);
        setStatusLoading(false);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setStatusLoading(false);
        failWith(error, setStatusError);
      });

    return () => controller.abort();
  }, [token, reloadToken, failWith]);

  // ---- Poll while a sync is running (started here or elsewhere) ----
  const running = token !== null && status?.status === 'running';

  useEffect(() => {
    if (!running) return;

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchSyncStatus(controller.signal)
        .then((next) => {
          setStatus(next);
          setStatusError(null);
          if (next.status === 'completed') {
            showToast(completionToast(next), 'success');
            setReloadToken((value) => value + 1); // also refreshes the count
          }
        })
        .catch((error: unknown) => {
          if (isAbortError(error)) return;
          if (isUnauthorized(error)) {
            reportUnauthorized();
            return;
          }
          // Transient polling failure: keep the last known state and retry.
        })
        .finally(() => {
          if (!controller.signal.aborted) setPollTick((value) => value + 1);
        });
    }, STATUS_POLL_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [running, pollTick, showToast, reportUnauthorized]);

  // ---- Console milestones from real status transitions ----
  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = status;
    if (!status) return;

    const run = runRef.current;

    if (status.status === 'running') {
      const syncId = status.syncId ?? null;
      if (run.syncId !== syncId) {
        run.syncId = syncId;
        run.fetching = false;
        run.listFetched = false;
        run.lastProcessed = null;
        const id = syncId ? syncId.slice(0, 8) : '????????';
        pushLine('info', `▸ sync ${id} started — ${formatCount(status.totalJobsBeforeSync)} jobs in the database`);
      }

      if (typeof status.jobsTotal === 'number') {
        if (!run.listFetched) {
          run.listFetched = true;
          pushLine('info', `→ source list fetched — ${formatCount(status.jobsTotal)} jobs`);
        }
        if (status.jobsProcessed !== run.lastProcessed && typeof status.jobsProcessed === 'number') {
          run.lastProcessed = status.jobsProcessed;
          pushLine('dim', progressLine(status));
        }
      } else if (!run.fetching) {
        run.fetching = true;
        pushLine('info', '→ fetching the job list from SuperSet…');
      }
      return;
    }

    // Terminal states: emit once per transition (never on the initial load).
    if (!prev || (prev.syncId ?? null) !== (status.syncId ?? null) || prev.status === status.status) return;

    if (status.status === 'completed') {
      pushLine('success', `✓ ${status.message ?? 'Sync completed'}`);
      pushLine('success', completionLine(status));
    } else if (status.status === 'failed') {
      pushLine('error', `✗ ${status.error ?? status.message ?? 'Sync failed'}`);
    }
  }, [status, pushLine]);

  const reload = useCallback(() => {
    setStartError(null);
    pushLine('dim', '→ reloading job count and sync status');
    setReloadToken((value) => value + 1);
  }, [pushLine]);

  const start = useCallback(async () => {
    if (!token) return;
    setStarting(true);
    setStartError(null);
    pushLine('cmd', '$ POST /api/admin/jobs/sync');

    try {
      await startJobSync();
      pushLine('info', '→ sync accepted — attaching to live status');
      setStatus(await fetchSyncStatus());
      setStatusError(null);
      showToast('Job synchronization started.', 'info');
    } catch (error: unknown) {
      if (isAbortError(error)) return;
      if (isUnauthorized(error)) {
        reportUnauthorized();
        return;
      }
      if (error instanceof ApiError && error.httpStatus === 409) {
        // Already running (double click / another tab) — adopt the live status.
        pushLine('warn', `! ${messageOf(error)}`);
        try {
          const live = await fetchSyncStatus();
          setStatus(live);
          setStatusError(null);
          if (live.status === 'running') pushLine('dim', '  attached to the operation already in progress');
        } catch (statusError: unknown) {
          failWith(statusError, setStartError);
        }
        return;
      }
      failWith(error, setStartError);
    } finally {
      setStarting(false);
    }
  }, [token, pushLine, showToast, reportUnauthorized, failWith]);

  const remove = useCallback(async () => {
    if (!token) return;
    setDeleting(true);
    pushLine('cmd', '$ DELETE /api/admin/jobs');
    pushLine('dim', '› removing job records, then the stored documents…');

    try {
      const result = await deleteAllJobs();

      for (const phase of result.phases ?? []) {
        pushLine('success', `✓ ${phase.phase} — ${phase.durationMs}ms`);
      }

      const summary = [
        `${formatCount(result.jobsDeleted)} jobs`,
        `${formatCount(result.documentRowsDeleted)} document records`,
        `${formatCount(result.filesDeleted)} files`,
      ].join(' · ');
      pushLine('success', `✓ deleted ${summary}`);

      if ((result.filesMissing ?? 0) > 0) {
        pushLine('dim', `  ${result.filesMissing} referenced files were already absent`);
      }
      if ((result.filesFailed ?? 0) > 0) {
        pushLine('warn', `  ${result.filesFailed} files could not be removed`);
      }
      if (typeof result.durationMs === 'number') {
        pushLine('dim', `  completed in ${result.durationMs}ms`);
      }

      showToast(result.message || 'All jobs deleted.', 'success');
      setReloadToken((value) => value + 1); // the count drops to 0
    } catch (error: unknown) {
      if (isAbortError(error)) return;
      if (isUnauthorized(error)) {
        reportUnauthorized();
        return;
      }

      const message = messageOf(error);
      if (error instanceof ApiError && error.httpStatus === 409) {
        // A sync owns the slot — surface the real message and refresh state.
        pushLine('warn', `! ${message}`);
        setReloadToken((value) => value + 1);
      } else {
        pushLine('error', `✗ ${message}`);
        showToast(message, 'error');
      }
    } finally {
      setDeleting(false);
    }
  }, [token, pushLine, showToast, reportUnauthorized]);

  return {
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
    busy: starting || deleting || running,
    reload,
    start,
    remove,
  };
}
