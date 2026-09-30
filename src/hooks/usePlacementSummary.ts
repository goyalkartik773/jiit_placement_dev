import { useCallback, useEffect, useState } from 'react';
import { ApiError, isAbortError } from '../services/apiClient';
import { fetchCompanyPlacements } from '../services/placementService';
import type { CompanyRow } from '../types/dashboard.types';

/**
 * Company-wide aggregates for the client Dashboard.
 *
 * Everything here is derived from the ONE read-only endpoint the Company-Wise
 * screen already uses — GET /api/placements/company-wise — which the backend
 * caps at 100 rows a page, so every page is fetched and summed client-side.
 * No number is invented: each one is a sum, a count or an extreme over rows
 * that the API actually returned.
 */

const PAGE_SIZE = 100; // backend maximum (PlacementController clamps to 100)
const MAX_PAGES = 10; // 1000 companies — far beyond the corpus, a safety net

export interface PackageBand {
  label: string;
  /** Students placed by companies inside the band. */
  students: number;
  /** Companies in the band (only those that placed someone). */
  companies: number;
}

export interface PlacementSummary {
  /** TotalCount reported by the API — companies with at least one job. */
  companiesTotal: number;
  /** Rows actually read (<= companiesTotal when MAX_PAGES is hit). */
  companiesRead: number;
  /** Sum of `placedstudents` across every row. */
  studentsPlaced: number;
  /** Rows with placedstudents > 0. */
  companiesPlacing: number;
  /** Largest disclosed package seen among companies that placed someone. */
  highestPackage: number | null;
  /** Disclosed package weighted by students placed (see the page footnote). */
  averagePackage: number;
  /** How many placed students sit in a band with no disclosed package. */
  undisclosedStudents: number;
  /**
   * Distinct branch labels with at least one placed student — the union of
   * every row's `branches[]`, never a sum (a branch appearing at three
   * companies counts once).
   */
  streamsCovered: number;
  /** Distinct campus labels with at least one placed student (same union rule). */
  campusesCovered: number;
  bands: PackageBand[];
  /** Top companies by students placed (highest first). */
  topCompanies: CompanyRow[];
  /** Companies with the highest disclosed package (placed someone, package known). */
  topOffers: CompanyRow[];
  /** Companies with the most recent `lastplacedat`. */
  recentCompanies: CompanyRow[];
}

/**
 * The highest package the feed discloses for a company: the best role CTC
 * (from offer students) or the best job package, whichever is larger. Both
 * come back as annual INR; 0 / null means "not disclosed" and is never
 * treated as a real figure.
 */
export function disclosedPackage(row: CompanyRow): number {
  let best = 0;
  for (const role of row.roles ?? []) {
    if (typeof role.ctcmax === 'number' && role.ctcmax > best) best = role.ctcmax;
  }
  for (const job of row.jobs ?? []) {
    if (typeof job.package === 'number' && job.package > best) best = job.package;
  }
  return best;
}

const BANDS: { label: string; min: number; max: number }[] = [
  { label: 'Under ₹5L', min: 0, max: 500_000 },
  { label: '₹5L – ₹10L', min: 500_000, max: 1_000_000 },
  { label: '₹10L – ₹20L', min: 1_000_000, max: 2_000_000 },
  { label: '₹20L and above', min: 2_000_000, max: Infinity },
];

function bandLabel(pkg: number): string {
  return BANDS.find((band) => pkg >= band.min && pkg < band.max)?.label ?? BANDS[BANDS.length - 1].label;
}

/** Fold every row into the four hero numbers, the band chart and the strips. */
export function summarize(rows: CompanyRow[], companiesTotal: number): PlacementSummary {
  // Pages are read sequentially, but TotalCount can move between them, so a
  // company may legitimately appear twice. Count each one exactly once.
  const byCompany = new Map<string, CompanyRow>();
  for (const row of rows) {
    if (!row || typeof row.company !== 'string') continue;
    if (!byCompany.has(row.company)) byCompany.set(row.company, row);
  }
  const unique = [...byCompany.values()];

  let studentsPlaced = 0;
  let companiesPlacing = 0;
  let highestPackage = 0;
  let weightedPackage = 0;
  let weightedStudents = 0;
  let undisclosedStudents = 0;

  const bandMap = new Map<string, PackageBand>();
  for (const band of BANDS) bandMap.set(band.label, { label: band.label, students: 0, companies: 0 });

  // Coverage is a SET union, not a sum: the same branch/campus at three
  // companies is one stream/campus, and a label of "" must never become one.
  const streams = new Set<string>();
  const campuses = new Set<string>();

  for (const row of unique) {
    const placed = Number(row.placedstudents) || 0;
    if (placed <= 0) continue;
    companiesPlacing += 1;
    studentsPlaced += placed;

    for (const item of row.branches ?? []) {
      const label = (item?.branch ?? '').trim();
      if (label) streams.add(label);
    }
    for (const item of row.campuses ?? []) {
      const label = (item?.campus ?? '').trim();
      if (label) campuses.add(label);
    }

    const pkg = disclosedPackage(row);
    if (pkg > 0) {
      if (pkg > highestPackage) highestPackage = pkg;
      weightedPackage += pkg * placed;
      weightedStudents += placed;
      const band = bandMap.get(bandLabel(pkg));
      if (band) {
        band.students += placed;
        band.companies += 1;
      }
    } else {
      undisclosedStudents += placed;
    }
  }

  const byPlaced = [...unique].sort((a, b) => (b.placedstudents || 0) - (a.placedstudents || 0));
  // Ranked by the package itself, never by headcount: a company that placed
  // many students at a low package must not read as a "top offer".
  const byPackage = unique
    .filter((row) => (Number(row.placedstudents) || 0) > 0 && disclosedPackage(row) > 0)
    .sort((a, b) => disclosedPackage(b) - disclosedPackage(a));
  const byRecent = [...unique]
    .filter((row) => row.lastplacedat && row.placedstudents > 0)
    .sort((a, b) => Date.parse(b.lastplacedat!) - Date.parse(a.lastplacedat!));

  return {
    companiesTotal,
    companiesRead: unique.length,
    studentsPlaced,
    companiesPlacing,
    highestPackage: highestPackage > 0 ? highestPackage : null,
    averagePackage: weightedStudents > 0 ? Math.round(weightedPackage / weightedStudents) : 0,
    undisclosedStudents,
    streamsCovered: streams.size,
    campusesCovered: campuses.size,
    bands: BANDS.map((band) => bandMap.get(band.label)!),
    topCompanies: byPlaced.slice(0, 6),
    topOffers: byPackage.slice(0, 6),
    recentCompanies: byRecent.slice(0, 6),
  };
}

export interface UsePlacementSummaryState {
  summary: PlacementSummary | null;
  /** True only for the first load (drives skeletons). */
  loading: boolean;
  error: ApiError | Error | null;
}

export function usePlacementSummary(): UsePlacementSummaryState & { reload: () => void } {
  const [state, setState] = useState<UsePlacementSummaryState>({
    summary: null,
    loading: true,
    error: null,
  });
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) => ({ summary: prev.summary, loading: prev.summary === null, error: null }));

    (async () => {
      try {
        const first = await fetchCompanyPlacements({ page: 1, pageSize: PAGE_SIZE }, controller.signal);
        const pages = Math.max(1, Math.min(Math.ceil(first.totalCount / PAGE_SIZE), MAX_PAGES));
        let rows = first.items;

        for (let page = 2; page <= pages; page += 1) {
          const next = await fetchCompanyPlacements({ page, pageSize: PAGE_SIZE }, controller.signal);
          if (next.items.length === 0) break;
          rows = rows.concat(next.items);
        }

        if (controller.signal.aborted) return;
        setState({ summary: summarize(rows, first.totalCount), loading: false, error: null });
      } catch (error) {
        if (controller.signal.aborted || isAbortError(error)) return;
        setState((prev) => ({ summary: prev.summary, loading: false, error: error as Error }));
      }
    })();

    return () => controller.abort();
  }, [retryToken]);

  const reload = useCallback(() => setRetryToken((token) => token + 1), []);
  return { ...state, reload };
}
