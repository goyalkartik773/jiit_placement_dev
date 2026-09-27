import { getJson } from './apiClient';
import type { ApiEnvelope } from '../types/job.types';
import type {
  EmailNoticeListData,
  EmailNoticeParams,
  NoticeFacet,
  SupersetNoticeListData,
  SupersetNoticeParams,
  SupersetNotice,
  EmailNotice,
} from '../types/dashboard.types';

/**
 * Notice API service - the ONLY place that knows notice endpoint paths.
 *
 * GET /api/notices/email?page&pageSize&search&type   (parsed placement emails)
 * GET /api/notices?page&pageSize&search              (Superset portal notices)
 */
export interface FetchedEmailNotices {
  items: EmailNotice[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
  /** Classification buckets for the current search (type filter ignored). */
  facets: NoticeFacet[];
}

export interface FetchedSupersetNotices {
  items: SupersetNotice[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

function toPositiveInt(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : fallback;
}

/** Unwraps one list envelope: null Items -> [], everything else server-owned. */
function unwrapList<T>(
  data: { Items: T[] | null; TotalCount: number; Page: number; PageSize: number; TotalPages: number } | null,
  page: number,
  pageSize: number,
): { items: T[]; totalCount: number; page: number; pageSize: number; totalPages: number } {
  const items = Array.isArray(data?.Items) ? data.Items.filter((item) => item && typeof item === 'object') : [];
  const totalCount = toPositiveInt(data?.TotalCount, 0);
  const resolvedPageSize = toPositiveInt(data?.PageSize, pageSize);

  return {
    items,
    totalCount,
    page: toPositiveInt(data?.Page, page),
    pageSize: resolvedPageSize,
    totalPages: toPositiveInt(data?.TotalPages, Math.max(1, Math.ceil(totalCount / resolvedPageSize))),
  };
}

/**
 * Fetches one page of email notices.
 * `type` is the UPPERCASE classification (e.g. "SHORTLIST"); send "" for all.
 */
export async function fetchEmailNotices(
  params: EmailNoticeParams = {},
  signal?: AbortSignal,
): Promise<FetchedEmailNotices> {
  const page = toPositiveInt(params.page, 1);
  const pageSize = toPositiveInt(params.pageSize, 20);

  const query = new URLSearchParams();
  query.set('page', String(page));
  query.set('pageSize', String(pageSize));
  if (params.search?.trim()) query.set('search', params.search.trim());
  if (params.type?.trim()) query.set('type', params.type.trim());

  const envelope = await getJson<ApiEnvelope<EmailNoticeListData>>(`/api/notices/email?${query.toString()}`, { signal });

  const rawFacets = envelope.Data?.Facets;
  const facets = Array.isArray(rawFacets) ? rawFacets.filter((facet) => facet && typeof facet === 'object') : [];

  return { ...unwrapList<EmailNotice>(envelope.Data, page, pageSize), facets };
}

/** Fetches one page of Superset portal notices (unchanged existing endpoint). */
export async function fetchSupersetNotices(
  params: SupersetNoticeParams = {},
  signal?: AbortSignal,
): Promise<FetchedSupersetNotices> {
  const page = toPositiveInt(params.page, 1);
  const pageSize = toPositiveInt(params.pageSize, 20);

  const query = new URLSearchParams();
  query.set('page', String(page));
  query.set('pageSize', String(pageSize));
  if (params.search?.trim()) query.set('search', params.search.trim());

  const envelope = await getJson<ApiEnvelope<SupersetNoticeListData>>(`/api/notices?${query.toString()}`, { signal });

  return unwrapList<SupersetNotice>(envelope.Data, page, pageSize);
}
