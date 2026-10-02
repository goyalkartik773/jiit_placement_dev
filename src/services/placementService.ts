import { getJson } from './apiClient';
import type { ApiEnvelope } from '../types/job.types';
import type {
  BranchStat,
  BranchStatBand,
  BranchStatFineBand,
  BranchStatsData,
  BranchStatsSummary,
  BranchTimelineDayPoint,
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

/**
 * The 15 fixed CTC bands (`fine_bands` in the SQL). Same defensive shape as
 * `toBands`, but the count is named `offers` — this axis counts offers, not
 * distinct students, so the two must not be confused.
 */
function toFineBands(value: unknown): BranchStatFineBand[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((band) => band && typeof band === 'object')
    .map((band) => ({
      band: typeof band.band === 'string' && band.band.trim() ? band.band.trim() : 'Unknown band',
      offers: toFiniteNumber(band.offers, 0),
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
    finedistribution: toFineBands(data.finedistribution),
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

/**
 * Package and cumulative fields are OPTIONAL on the wire (the endpoint only
 * reports them where it can), so each is copied only when genuinely present.
 * Copying `undefined` would be indistinguishable from "not reported" — but
 * `null` IS reported here, and it means "no disclosed package", so `null` is
 * passed through rather than dropped.
 */
/**
 * Copy an optional `number | null` field only when it is genuinely present.
 * `null` IS reported here and means "no disclosed package", so it is preserved;
 * a missing key stays missing so the UI can tell "not reported" from "zero".
 */
function copyNullable(target: object, source: object, key: string): void {
  if (!(key in source)) return;
  const raw = (source as Record<string, unknown>)[key];
  if (raw === undefined) return;
  (target as Record<string, unknown>)[key] = toNullableNumber(raw);
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

  // Per-bucket package figures.
  if (data.studentswithpackage !== undefined && data.studentswithpackage !== null) {
    point.studentswithpackage = toFiniteNumber(data.studentswithpackage, 0);
  }
  copyNullable(point, data, 'averagepackage');
  copyNullable(point, data, 'medianpackage');

  // Cumulative twins. `cumstudents` and `cumstudentswithpackage` are counts and
  // can legitimately be 0, so they are presence-checked, not value-checked.
  if (data.cumoffers !== undefined && data.cumoffers !== null) {
    point.cumoffers = toFiniteNumber(data.cumoffers, 0);
  }
  if (data.cumstudents !== undefined && data.cumstudents !== null) {
    point.cumstudents = toFiniteNumber(data.cumstudents, 0);
  }
  if (data.cumstudentswithpackage !== undefined && data.cumstudentswithpackage !== null) {
    point.cumstudentswithpackage = toFiniteNumber(data.cumstudentswithpackage, 0);
  }
  copyNullable(point, data, 'cumaveragepackage');
  copyNullable(point, data, 'cummedianpackage');

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
 * Daily bucket (ISO `YYYY-MM-DD`). Identical field set to the monthly point —
 * only the key differs — so it reuses `toTimelinePoint` and re-keys the result
 * rather than duplicating the optional-field handling.
 */
function toDailyPoint(value: unknown): BranchTimelineDayPoint | null {
  const point = toTimelinePoint(value);
  if (!point) return null;
  const raw = (value ?? {}) as { day?: unknown };
  const day = typeof raw.day === 'string' ? raw.day.trim() : '';
  if (!day) return null;

  // Built field by field: the two shapes differ by their key (`day` vs
  // `month`), and spreading `point` would carry `month` along with it.
  const daily: BranchTimelineDayPoint = { day, offers: point.offers, students: point.students };
  if (point.companies !== undefined) daily.companies = point.companies;
  if (point.studentswithpackage !== undefined) daily.studentswithpackage = point.studentswithpackage;
  // `null` is a reported "not disclosed" and is preserved; `undefined` means
  // the endpoint did not report it at all and stays absent.
  if (point.averagepackage !== undefined) daily.averagepackage = point.averagepackage;
  if (point.medianpackage !== undefined) daily.medianpackage = point.medianpackage;
  if (point.cumoffers !== undefined) daily.cumoffers = point.cumoffers;
  if (point.cumstudents !== undefined) daily.cumstudents = point.cumstudents;
  if (point.cumstudentswithpackage !== undefined) daily.cumstudentswithpackage = point.cumstudentswithpackage;
  if (point.cumaveragepackage !== undefined) daily.cumaveragepackage = point.cumaveragepackage;
  if (point.cummedianpackage !== undefined) daily.cummedianpackage = point.cummedianpackage;
  return daily;
}

/**
 * Cache for the branch-wise block — the entire Analytics page hangs off this
 * one payload, and re-entering the route used to re-download it AND re-run
 * every normaliser before a single figure could be printed. Same 60-second
 * window as the company feed: come back inside a minute and the page is
 * already painted with data rather than a skeleton.
 */
let branchStatsCache: { value: BranchStatsData; at: number } | null = null;
const BRANCH_STATS_TTL_MS = 60_000;

/**
 * Fetches the branch-wise statistics block for the graduating batch.
 * Normalises every field defensively: the section must render honest zeroes
 * and em-dashes rather than "undefined" if the payload is ever incomplete.
 */
export async function fetchBranchStats(signal?: AbortSignal): Promise<BranchStatsData> {
  if (branchStatsCache && Date.now() - branchStatsCache.at < BRANCH_STATS_TTL_MS) {
    return branchStatsCache.value;
  }

  const value = await requestBranchStats(signal);
  // Only a COMPLETED read is kept. An abort throws before this line, so the
  // cache stays empty and the next mount tries again instead of serving a
  // half-cancelled payload.
  branchStatsCache = { value, at: Date.now() };
  return value;
}

async function requestBranchStats(signal?: AbortSignal): Promise<BranchStatsData> {
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

  const daily = (Array.isArray(data?.daily) ? data.daily : [])
    .map(toDailyPoint)
    .filter((row): row is BranchTimelineDayPoint => row !== null);

  return {
    batch: typeof data?.batch === 'string' && data.batch.trim() ? data.batch.trim() : '',
    graduatingbatch: toFiniteNumber(data?.graduatingbatch, 0),
    generatedat: typeof data?.generatedat === 'string' ? data.generatedat : '',
    currency: typeof data?.currency === 'string' && data.currency.trim() ? data.currency.trim() : 'LPA',
    branches,
    totals: toSummary(data?.totals),
    timeline,
    branchtimeline,
    daily,
  };
}
