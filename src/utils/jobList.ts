import type { JobListItem } from '../types/job.types';

/**
 * Client-side refinement helpers for the job list.
 *
 * The backend supports server-side `search`, `company` and pagination only.
 * Location / status / category refinement and sorting therefore run here —
 * but ONLY when the complete result set is loaded (see Jobs page), so that
 * every count shown to the user stays truthful.
 */

export type SortKey = 'newest' | 'oldest' | 'title-asc' | 'package-desc';

export interface JobFilters {
  location: string;
  status: string;
  category: string;
  sort: SortKey;
}

export const DEFAULT_FILTERS: JobFilters = {
  location: '',
  status: '',
  category: '',
  sort: 'newest',
};

export function hasActiveFilters(filters: JobFilters): boolean {
  return Boolean(filters.location || filters.status || filters.category) || filters.sort !== DEFAULT_FILTERS.sort;
}

export function applyFilters(items: JobListItem[], filters: JobFilters): JobListItem[] {
  const filtered = items.filter((job) => {
    if (filters.location && job.location !== filters.location) return false;
    if (filters.status && job.status !== filters.status) return false;
    if (filters.category && job.placementcategory !== filters.category) return false;
    return true;
  });

  const sorted = [...filtered];
  switch (filters.sort) {
    case 'oldest':
      sorted.sort((a, b) => toSortKey(a).localeCompare(toSortKey(b)));
      break;
    case 'title-asc':
      sorted.sort((a, b) => a.jobprofile.localeCompare(b.jobprofile, undefined, { sensitivity: 'base' }));
      break;
    case 'package-desc':
      sorted.sort((a, b) => (b.package ?? 0) - (a.package ?? 0));
      break;
    case 'newest':
    default:
      // Matches the API's own ordering (createdat DESC) — nothing to do.
      break;
  }
  return sorted;
}

/** Distinct, sorted values for the refinement selects — derived, never stored. */
export function extractFilterOptions(items: JobListItem[]): {
  locations: string[];
  statuses: string[];
  categories: string[];
} {
  return {
    locations: uniqueSorted(items.map((job) => job.location)),
    statuses: uniqueSorted(items.map((job) => job.status)),
    categories: uniqueSorted(items.map((job) => job.placementcategory)),
  };
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function toSortKey(job: JobListItem): string {
  return job.posteddatetime ?? job.createdat ?? '';
}
