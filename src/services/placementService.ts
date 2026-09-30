import { getJson } from './apiClient';
import type { ApiEnvelope } from '../types/job.types';
import type {
  BranchStat,
  BranchStatBand,
  BranchStatsData,
  BranchStatsSummary,
  BranchTimelinePoint,
  BranchTimelineSeriesPoint,
  CompanyRow,
  CompanyWiseListData,
  CompanyWiseParams,
  PlacedStudentsData,
  PlacedStudent,
} from '../types/dashboard.types';

/**
 * Placement API service - the ONLY place that knows placement endpoint paths.
 *
 * GET /api/placements/company-wise?page&pageSize&search
 * GET /api/placements/branch-stats
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

/* -------------------------------------------------------------------------- */
/* Branch-wise statistics                                                       */
/* -------------------------------------------------------------------------- */

function toFiniteNumber(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/** JSON null / undefined / "" -> null; anything unparseable -> null too. */
function toNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function toBands(value: unknown): BranchStatBand[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((band) => band && typeof band === 'object')
    .map((band) => ({
      band: typeof band.band === 'string' && band.band.trim() ? band.band.trim() : 'Unknown band',
      students: toFiniteNumber(band.students, 0),
    }));
}

function toSummary(value: unknown): BranchStatsSummary {
  const data = (value ?? {}) as Partial<BranchStatsSummary>;
  return {
    totalstudents: toFiniteNumber(data.totalstudents, 0),
    placedstudents: toFiniteNumber(data.placedstudents, 0),
    placementpercentage: toFiniteNumber(data.placementpercentage, 0),
    totaloffers: toFiniteNumber(data.totaloffers, 0),
    companies: toFiniteNumber(data.companies, 0),
    studentswithpackage: toFiniteNumber(data.studentswithpackage, 0),
    averagepackage: toNullableNumber(data.averagepackage),
    medianpackage: toNullableNumber(data.medianpackage),
    highestpackage: toNullableNumber(data.highestpackage),
    distribution: toBands(data.distribution),
  };
}

function toBranchStat(value: unknown): BranchStat | null {
  if (!value || typeof value !== 'object') return null;
  const branch = typeof (value as { branch?: unknown }).branch === 'string'
    ? String((value as { branch?: unknown }).branch).trim()
    : '';
  if (!branch) return null;
  return { ...toSummary(value), branch };
}

function toTimelinePoint(value: unknown): BranchTimelinePoint | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as Partial<BranchTimelinePoint> & { branch?: unknown };
  const month = typeof data.month === 'string' ? data.month.trim() : '';
  if (!month) return null;

  const point: BranchTimelinePoint = {
    month,
    offers: toFiniteNumber(data.offers, 0),
    students: toFiniteNumber(data.students, 0),
  };
  // Present on the overall series only; absent there means "not reported".
  if (data.companies !== null && data.companies !== undefined) {
    point.companies = toFiniteNumber(data.companies, 0);
  }
  return point;
}

function toSeriesPoint(value: unknown): BranchTimelineSeriesPoint | null {
  const point = toTimelinePoint(value);
  if (!point) return null;
  const raw = (value ?? {}) as { branch?: unknown };
  const branch = typeof raw.branch === 'string' ? raw.branch.trim() : '';
  if (!branch) return null;
  return { ...point, branch };
}

/**
 * Fetches the branch-wise statistics block for the graduating batch.
 * Normalises every field defensively: the section must render honest zeroes
 * and em-dashes rather than "undefined" if the payload is ever incomplete.
 */
export async function fetchBranchStats(signal?: AbortSignal): Promise<BranchStatsData> {
  const envelope = await getJson<ApiEnvelope<BranchStatsData>>('/api/placements/branch-stats', { signal });
  const data = envelope.Data;

  const branches = (Array.isArray(data?.branches) ? data.branches : [])
    .map(toBranchStat)
    .filter((row): row is BranchStat => row !== null);

  const timeline = (Array.isArray(data?.timeline) ? data.timeline : [])
    .map(toTimelinePoint)
    .filter((row): row is BranchTimelinePoint => row !== null);

  const branchtimeline = (Array.isArray(data?.branchtimeline) ? data.branchtimeline : [])
    .map(toSeriesPoint)
    .filter((row): row is BranchTimelineSeriesPoint => row !== null);

  return {
    batch: typeof data?.batch === 'string' && data.batch.trim() ? data.batch.trim() : '',
    graduatingbatch: toFiniteNumber(data?.graduatingbatch, 0),
    generatedat: typeof data?.generatedat === 'string' ? data.generatedat : '',
    currency: typeof data?.currency === 'string' && data.currency.trim() ? data.currency.trim() : 'LPA',
    branches,
    totals: toSummary(data?.totals),
    timeline,
    branchtimeline,
  };
}
