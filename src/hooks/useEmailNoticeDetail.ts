import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { fetchEmailNoticeDetail } from '../services/noticeService';
import type { EmailNoticeDetail } from '../types/dashboard.types';

export interface UseEmailNoticeDetailState {
  /** null while nothing is selected - the workspace shows its empty state. */
  id: string | null;
  detail: EmailNoticeDetail | null;
  /** True only for the first load of this id (no payload yet). */
  loading: boolean;
  error: ApiError | Error | null;
}

/**
 * The reading pane's payload: one detail at a time, re-fetched only for an
 * id this mount has not already seen.
 *
 * The cache lives in a ref rather than state on purpose. It has to survive
 * re-renders and switching between notices (so flipping back never re-hits
 * the API, which is what the old per-card cache did), but it must NOT be a
 * dependency of the effect below - a Map written into state would wake the
 * effect, which would read the same Map, and so on. Reads are therefore
 * imperative; the Map's identity never reaches the dependency array.
 *
 * Selection is cleared by passing null, which drops back to idle rather than
 * aborting a fetch: nothing is in flight when nothing is selected.
 */
export function useEmailNoticeDetail(id: string | null): UseEmailNoticeDetailState & { reload: () => void } {
  const cacheRef = useRef(new Map<string, EmailNoticeDetail>());
  const [state, setState] = useState<UseEmailNoticeDetailState>({
    id: null,
    detail: null,
    loading: false,
    error: null,
  });
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (!id) {
      setState({ id: null, detail: null, loading: false, error: null });
      return;
    }

    const cached = cacheRef.current.get(id);
    if (cached) {
      setState({ id, detail: cached, loading: false, error: null });
      return;
    }

    const controller = new AbortController();
    setState({ id, detail: null, loading: true, error: null });

    fetchEmailNoticeDetail(id, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        cacheRef.current.set(id, data);
        setState({ id, detail: data, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || controller.signal.aborted) return;
        const normalized = error instanceof Error ? error : new Error('Could not load this email.');
        setState((prev) => ({ ...prev, loading: false, error: normalized }));
      });

    return () => controller.abort();
  }, [id, retryToken]);

  const reload = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, reload };
}
