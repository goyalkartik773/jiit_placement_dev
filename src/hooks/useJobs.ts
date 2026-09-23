import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { fetchJobs, type FetchedJobs } from '../services/jobService';

export interface UseJobsState {
  data: FetchedJobs | null;
  /** True only for the first load (no data yet) — drives skeletons. */
  initialLoading: boolean;
  /** True while re-fetching with data already on screen — drives subtle progress. */
  refreshing: boolean;
  error: ApiError | Error | null;
}

/**
 * Server-driven job list: page, pageSize and search are sent to the backend
 * (fn_api_select_jobs_v1 supports all three + company). Requests are cancelled
 * when parameters change so stale responses never overwrite fresh ones.
 */
export function useJobs(page: number, pageSize: number, search: string): UseJobsState & { reload: () => void } {
  const [state, setState] = useState<UseJobsState>({ data: null, initialLoading: true, refreshing: false, error: null });
  const [retryToken, setRetryToken] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState((prev) => ({
      data: prev.data,
      initialLoading: prev.data === null,
      refreshing: prev.data !== null,
      error: null,
    }));

    fetchJobs({ page, pageSize, search }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setState({ data, initialLoading: false, refreshing: false, error: null });
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || controller.signal.aborted) return;
        const normalized = error instanceof Error ? error : new Error('Unexpected error while loading jobs.');
        setState((prev) => ({ data: prev.data, initialLoading: false, refreshing: false, error: normalized }));
      });

    return () => controller.abort();
  }, [page, pageSize, search, retryToken]);

  const reload = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, reload };
}
