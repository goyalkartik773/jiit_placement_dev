import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { getOverview } from '../services/adminService';
import type { AdminOverview } from '../types/admin.types';

export interface AdminOverviewState {
  overview: AdminOverview | null;
  /** True only for the first load (no data yet) — drives skeletons. */
  initialLoading: boolean;
  /** True while re-fetching with data already on screen — drives the refresh button. */
  refreshing: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * GET /api/admin/overview with the cancellable pattern used across the app:
 * one AbortController per request, aborted on unmount/parameter change, 401s
 * reported upward so the session can be dropped exactly once.
 */
export function useAdminOverview(token: string | null, onUnauthorized: () => void): AdminOverviewState {
  const [state, setState] = useState<{
    overview: AdminOverview | null;
    initialLoading: boolean;
    refreshing: boolean;
    error: string | null;
  }>({ overview: null, initialLoading: token !== null, refreshing: false, error: null });
  const [retryToken, setRetryToken] = useState(0);

  // Always call the freshest callback (it closes over the current token).
  const onUnauthorizedRef = useRef(onUnauthorized);
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
  }, [onUnauthorized]);

  useEffect(() => {
    if (!token) {
      setState({ overview: null, initialLoading: false, refreshing: false, error: null });
      return;
    }

    const controller = new AbortController();
    setState((prev) => ({
      overview: prev.overview,
      initialLoading: prev.overview === null,
      refreshing: prev.overview !== null,
      error: null,
    }));

    getOverview(controller.signal)
      .then((overview) => {
        if (controller.signal.aborted) return;
        setState({ overview, initialLoading: false, refreshing: false, error: null });
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted || isAbortError(caught)) return;
        if (caught instanceof ApiError && caught.httpStatus === 401) {
          onUnauthorizedRef.current();
          return;
        }
        const message = caught instanceof Error ? caught.message : 'Could not load the console overview.';
        setState((prev) => ({
          overview: prev.overview,
          initialLoading: false,
          refreshing: false,
          error: message,
        }));
      });

    return () => controller.abort();
  }, [token, retryToken]);

  const reload = useCallback(() => setRetryToken((value) => value + 1), []);

  return { ...state, reload };
}
