import { getJson } from './apiClient';
import type { ApiEnvelope } from '../types/job.types';
import type {
  CompanyRow,
  CompanyWiseListData,
  CompanyWiseParams,
  PlacedStudentsData,
  PlacedStudent,
} from '../types/dashboard.types';

/**
 * Placement API service — the ONLY place that knows placement endpoint paths.
 *
 * GET /api/placements/company-wise?page&pageSize&search
 * GET /api/placements/jobs/{jobId}/placed-students
 */
export interface FetchedCompanyPlacements {
  items: CompanyRow[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface FetchedPlacedStudents {
  job: PlacedStudentsData['job'];
  placedCount: number;
  students: PlacedStudent[];
}

function toPositiveInt(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : fallback;
}

/**
 * Fetches one page of the company-wise placement summary
 * (sorted server-side by placed students DESC, then company ASC).
 * Defensive against null/missing API fields.
 */
export async function fetchCompanyPlacements(
  params: CompanyWiseParams = {},
  signal?: AbortSignal,
): Promise<FetchedCompanyPlacements> {
  const page = toPositiveInt(params.page, 1);
  const pageSize = toPositiveInt(params.pageSize, 20);

  const query = new URLSearchParams();
  query.set('page', String(page));
  query.set('pageSize', String(pageSize));
  if (params.search?.trim()) query.set('search', params.search.trim());

  const envelope = await getJson<ApiEnvelope<CompanyWiseListData>>(
    `/api/placements/company-wise?${query.toString()}`,
    { signal },
  );

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
 * Fetches the offer students already matched to one job (roll no, branch,
 * role, CTC, offer date). Throws ApiError(404) when the job does not exist.
 */
export async function fetchPlacedStudents(jobId: string, signal?: AbortSignal): Promise<FetchedPlacedStudents> {
  const envelope = await getJson<ApiEnvelope<PlacedStudentsData>>(
    `/api/placements/jobs/${encodeURIComponent(jobId)}/placed-students`,
    { signal },
  );

  const data = envelope.Data;
  if (!data || !data.job || typeof data.job !== 'object') {
    throw new Error(envelope.Message || 'Job not found');
  }

  const students = Array.isArray(data.students) ? data.students.filter((row) => row && typeof row === 'object') : [];

  const placedCount =
    typeof data.placedCount === 'number' && Number.isFinite(data.placedCount) ? data.placedCount : students.length;

  return { job: data.job, placedCount, students };
}
