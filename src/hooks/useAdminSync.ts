import { useCallback, useEffect, useRef, useState } from 'react';
import { useToast } from '../components/common/Toast/Toast';
import { ApiError, isAbortError } from '../services/apiClient';
import { fetchAdminJobCount, fetchSyncStatus, startJobSync } from '../services/adminService';
import type { AdminSyncStatus } from '../types/admin.types';

/** Server-side syncs take minutes; 2s keeps the progress honest without hammering the API. */
const STATUS_POLL_MS = 2000;

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

export interface AdminSyncController {
  count: number | null;
  countLoading: boolean;
  countError: string | null;
  status: AdminSyncStatus | null;
  statusLoading: boolean;
  statusError: string | null;
  starting: boolean;
  startError: string | null;
  /** Re-fetch count + status (also the retry path for every load error). */
  reload: () => void;
  /** Start a sync. A 409 ("already running") simply adopts the live status. */
  start: () => void;
}

/**
 * Drives the admin console:
 *  - loads the job count and sync status together (parallel, abortable),
 *  - starts a sync and then polls the status endpoint while it runs,
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

  const [reloadToken, setReloadToken] = useState(0);
  const [pollTick, setPollTick] = useState(0);

  // Always call the freshest callback (it closes over the current token).
  const onUnauthorizedRef = useRef(onUnauthorized);
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
  }, [onUnauthorized]);

  const failWith = useCallback((error: unknown, setError: (message: string | null) => void): void => {
    if (isAbortError(error)) return;
    if (isUnauthorized(error)) {
      onUnauthorizedRef.current();
      return;
    }
    setError(messageOf(error));
  }, []);

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
            onUnauthorizedRef.current();
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
  }, [running, pollTick, showToast]);

  const reload = useCallback(() => {
    setStartError(null);
    setReloadToken((value) => value + 1);
  }, []);

  const start = useCallback(async () => {
    if (!token) return;
    setStarting(true);
    setStartError(null);

    try {
      await startJobSync();
      showToast('Job synchronization started.', 'info');
      setStatus(await fetchSyncStatus());
      setStatusError(null);
    } catch (error: unknown) {
      if (isAbortError(error)) return;
      if (isUnauthorized(error)) {
        onUnauthorizedRef.current();
        return;
      }
      if (error instanceof ApiError && error.httpStatus === 409) {
        // Already running (double click / another tab) — adopt the live status.
        try {
          setStatus(await fetchSyncStatus());
          setStatusError(null);
        } catch (statusError: unknown) {
          failWith(statusError, setStartError);
        }
        return;
      }
      failWith(error, setStartError);
    } finally {
      setStarting(false);
    }
  }, [token, showToast, failWith]);

  return {
    count,
    countLoading,
    countError,
    status,
    statusLoading,
    statusError,
    starting,
    startError,
    reload,
    start,
  };
}
