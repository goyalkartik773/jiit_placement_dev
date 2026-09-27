import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { fetchEmailNotices, type FetchedEmailNotices } from '../services/noticeService';

export interface UseEmailNoticesState {
  data: FetchedEmailNotices | null;
  /** True only for the first load (no data yet) - drives skeletons. */
  initialLoading: boolean;
  /** True while re-fetching with data already on screen - drives subtle progress. */
  refreshing: boolean;
  error: ApiError | Error | null;
}

/**
 * Parsed email notices: page, pageSize, search and the UPPERCASE `type`
 * classification are sent to the backend. Requests are cancelled when
 * parameters change so stale responses never overwrite fresh ones.
 */
export function useEmailNotices(
  page: number,
  pageSize: number,
  search: string,
  type: string,
): UseEmailNoticesState & { reload: () => void } {
  const [state, setState] = useState<UseEmailNoticesState>({
    data: null,
    initialLoading: true,
    refreshing: false,
    error: null,
  });
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

    fetchEmailNotices({ page, pageSize, search, type }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setState({ data, initialLoading: false, refreshing: false, error: null });
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || controller.signal.aborted) return;
        const normalized = error instanceof Error ? error : new Error('Unexpected error while loading email notices.');
        setState((prev) => ({ data: prev.data, initialLoading: false, refreshing: false, error: normalized }));
      });

    return () => controller.abort();
  }, [page, pageSize, search, type, retryToken]);

  const reload = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, reload };
}
