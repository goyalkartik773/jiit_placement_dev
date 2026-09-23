import { getJson } from './apiClient';
import type {
  ApiEnvelope,
  JobDetail,
  JobDetailEnvelope,
  JobListParams,
  JobListItem,
  JobsListData,
} from '../types/job.types';

/**
 * Job API service — the ONLY place that knows job endpoint paths.
 *
 * GET /api/jobs?page&pageSize&company&search
 * GET /api/jobs/{id}
 */
export interface FetchedJobs {
  items: JobListItem[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

function toPositiveInt(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : fallback;
}

/** Fetches one page of jobs. Defensive against null/missing API fields. */
export async function fetchJobs(params: JobListParams = {}, signal?: AbortSignal): Promise<FetchedJobs> {
  const page = toPositiveInt(params.page, 1);
  const pageSize = toPositiveInt(params.pageSize, 20);

  const query = new URLSearchParams();
  query.set('page', String(page));
  query.set('pageSize', String(pageSize));
  if (params.company?.trim()) query.set('company', params.company.trim());
  if (params.search?.trim()) query.set('search', params.search.trim());

  const envelope = await getJson<ApiEnvelope<JobsListData>>(`/api/jobs?${query.toString()}`, { signal });

  // The backend can return Data = null (empty table / no rows) with status = true.
  const data = envelope.Data;
  const items = Array.isArray(data?.Items) ? data.Items.filter((item) => item && typeof item === 'object') : [];

  const totalCount = toPositiveInt(data?.TotalCount, 0);
  const currentPage = toPositiveInt(data?.Page, page);
  const resolvedPageSize = toPositiveInt(data?.PageSize, pageSize);
  const totalPages = toPositiveInt(
    data?.TotalPages,
    Math.max(1, Math.ceil(totalCount / resolvedPageSize)),
  );

  return { items, totalCount, page: currentPage, pageSize: resolvedPageSize, totalPages };
}

/**
 * Fetches the complete detail for one job.
 * Accepts the job UUID (or superset job identifier — both resolve server-side).
 * Throws ApiError(404) when the job does not exist.
 */
export async function fetchJobDetail(jobId: string, signal?: AbortSignal): Promise<JobDetail> {
  const envelope = await getJson<ApiEnvelope<JobDetailEnvelope>>(`/api/jobs/${encodeURIComponent(jobId)}`, { signal });

  const inner = envelope.Data;
  if (!inner || inner.status !== 'SUCCESS' || !inner.data || typeof inner.data !== 'object') {
    throw new Error(inner?.message || envelope.Message || 'Job not found');
  }
  return inner.data;
}
