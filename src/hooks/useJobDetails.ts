import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { fetchJobDetail } from '../services/jobService';
import type { JobDetail } from '../types/job.types';

interface UseJobDetailsState {
  job: JobDetail | null;
  loading: boolean;
  error: ApiError | Error | null;
  notFound: boolean;
}

/** Loads one job's complete detail (GET /api/jobs/{id}). */
export function useJobDetails(jobId: string | undefined): UseJobDetailsState & { reload: () => void } {
  const [state, setState] = useState<UseJobDetailsState>({ job: null, loading: true, error: null, notFound: false });
  const [retryToken, setRetryToken] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    if (!jobId) {
      setState({ job: null, loading: false, error: new Error('Missing job id.'), notFound: true });
      return () => controller.abort();
    }

    setState({ job: null, loading: true, error: null, notFound: false });

    fetchJobDetail(jobId, controller.signal)
      .then((job) => {
        if (controller.signal.aborted) return;
        setState({ job, loading: false, error: null, notFound: false });
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || controller.signal.aborted) return;
        const normalized = error instanceof Error ? error : new Error('Unexpected error while loading the job.');
        const notFound = normalized instanceof ApiError && normalized.httpStatus === 404;
        setState({ job: null, loading: false, error: normalized, notFound });
      });

    return () => controller.abort();
  }, [jobId, retryToken]);

  const reload = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, reload };
}
