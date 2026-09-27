import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { getActivity } from '../services/adminService';
import type { AdminActivityItem } from '../types/admin.types';

/** Matches the console contract (`?page=1&pageSize=12`); the timeline shows the first page. */
export const ACTIVITY_PAGE_SIZE = 12;

export interface AdminActivityState {
  /** Runs, newest first, appended page by page. */
  items: AdminActivityItem[];
  totalCount: number | null;
  totalPages: number | null;
  /** 1-based page of the last loaded page (0 before the first response). */
  page: number;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  hasMore: boolean;
  reload: () => void;
  loadMore: () => void;
}

/**
 * GET /api/admin/activity — page 1 loads (and reloads) the list, `loadMore`
 * fetches the next page and appends. Every request is abortable and a 401 is
 * reported upward so the session can be dropped exactly once.
 */
export function useActivity(token: string | null, onUnauthorized: () => void): AdminActivityState {
  const [items, setItems] = useState<AdminActivityItem[]>([]);
  const [totalCount, setTotalCount] = useState<number | null>(null);
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(token !== null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const onUnauthorizedRef = useRef(onUnauthorized);
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
  }, [onUnauthorized]);

  const moreAbortRef = useRef<AbortController | null>(null);
  useEffect(() => () => moreAbortRef.current?.abort(), []);

  const reportFailure = useCallback((caught: unknown, fallback: string): string | null => {
    if (caught instanceof ApiError && caught.httpStatus === 401) {
      onUnauthorizedRef.current();
      return null;
    }
    return caught instanceof Error ? caught.message : fallback;
  }, []);

  // ---- Page 1: initial load and manual reload ----
  useEffect(() => {
    // A reload supersedes any pending "load more".
    moreAbortRef.current?.abort();
    moreAbortRef.current = null;
    setLoadingMore(false);

    if (!token) {
      setItems([]);
      setTotalCount(null);
      setTotalPages(null);
      setPage(0);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getActivity({ page: 1, pageSize: ACTIVITY_PAGE_SIZE }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setItems(data.Items ?? []);
        setTotalCount(typeof data.TotalCount === 'number' ? data.TotalCount : null);
        setTotalPages(typeof data.TotalPages === 'number' ? data.TotalPages : null);
        setPage(typeof data.Page === 'number' ? data.Page : 1);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted || isAbortError(caught)) return;
        const message = reportFailure(caught, 'Could not load the activity log.');
        setLoading(false);
        if (message) setError(message);
      });

    return () => controller.abort();
  }, [token, reloadToken, reportFailure]);

  // ---- Load the next page and append ----
  const loadMore = useCallback(() => {
    if (!token || loading || loadingMore) return;
    const nextPage = page + 1;
    if (totalPages !== null && nextPage > totalPages) return;

    const controller = new AbortController();
    moreAbortRef.current = controller;
    setLoadingMore(true);

    getActivity({ page: nextPage, pageSize: ACTIVITY_PAGE_SIZE }, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setItems((prev) => [...prev, ...(data.Items ?? [])]);
        if (typeof data.Page === 'number') setPage(data.Page);
        if (typeof data.TotalPages === 'number') setTotalPages(data.TotalPages);
        if (typeof data.TotalCount === 'number') setTotalCount(data.TotalCount);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted || isAbortError(caught)) return;
        const message = reportFailure(caught, 'Could not load more runs.');
        if (message) setError(message);
      })
      .finally(() => {
        if (controller.signal.aborted) return;
        setLoadingMore(false);
        if (moreAbortRef.current === controller) moreAbortRef.current = null;
      });
  }, [token, loading, loadingMore, page, totalPages, reportFailure]);

  const reload = useCallback(() => setReloadToken((value) => value + 1), []);

  return {
    items,
    totalCount,
    totalPages,
    page,
    loading,
    loadingMore,
    error,
    hasMore: totalPages !== null && page > 0 && page < totalPages,
    reload,
    loadMore,
  };
}
