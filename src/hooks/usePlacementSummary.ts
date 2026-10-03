import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../services/apiClient';
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

export interface BranchTotal {
  /** Branch label exactly as the feed spells it ("CSE", "Intg. MTech"). */
  branch: string;
  /** Placed students in that branch, summed across every placing company. */
  students: number;
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
  /**
   * Placed students per branch, highest first — the sum over each placing
   * row's `branches[]`. Together with `studentsPlaced` this is the donut's
   * whole contract: the page folds the tail into "Other" and adds a
   * "Branch not stated" slice when a row arrived without a breakdown, so the
   * slices always add back up to `studentsPlaced`.
   */
  branchTotals: BranchTotal[];
  /**
   * Every company that placed someone AND discloses a package, ordered by
   * that package — highest first. This is the ranking behind the Dashboard's
   * "Top 5 companies" and Analytics' "Top companies", and it deliberately
   * ignores headcount: a firm hiring fifty students at a modest package must
   * not out-rank one paying double for two.
   *
   * Uncapped on purpose. The two screens take 5 and 10 rows, so a shared
   * `slice(0, 6)` would starve the wider one — callers cut what they show.
   */
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

  // Head-count per branch — the donut's feed. Same rule as `streams` below:
  // an empty label is never a branch, and each row's own count is what is
  // summed (the API ships `branches[].students` per company, so this stays a
  // pure sum over rows the feed actually returned).
  const branchMap = new Map<string, number>();

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
      if (!label) continue;
      streams.add(label);
      branchMap.set(label, (branchMap.get(label) ?? 0) + (Number(item.students) || 0));
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
    branchTotals: [...branchMap.entries()]
      .map(([branch, students]) => ({ branch, students }))
      .sort((a, b) => b.students - a.students || a.branch.localeCompare(b.branch)),
    topOffers: byPackage,
    recentCompanies: byRecent.slice(0, 6),
  };
}

export interface UsePlacementSummaryState {
  summary: PlacementSummary | null;
  /** True only for the first load (drives skeletons). */
  loading: boolean;
  error: ApiError | Error | null;
}

// --------------------------------------------------------------------------- #
// The shared read
// --------------------------------------------------------------------------- #

/**
 * How long a computed summary is served without going back to the API.
 *
 * The company feed is by a distance the most expensive read the client makes,
 * and the Dashboard and Analytics both ask for exactly the same rows. Sixty
 * seconds is long enough that moving between routes never re-pays it, and
 * short enough that a placement officer re-syncing the source sees their work
 * inside a minute. `reload()` ignores this window.
 */
const CACHE_TTL_MS = 60_000;

let cachedSummary: { value: PlacementSummary; at: number } | null = null;

/** The in-flight load, shared by every caller waiting on the same rows. */
let inflight: Promise<PlacementSummary> | null = null;

function freshSummary(): PlacementSummary | null {
  if (!cachedSummary) return null;
  if (Date.now() - cachedSummary.at >= CACHE_TTL_MS) {
    cachedSummary = null;
    return null;
  }
  return cachedSummary.value;
}

/**
 * Read every page of the company feed.
 *
 * Page 1 has to land first — it is the only thing that says how many pages
 * exist — and that used to gate a strictly serial `for` loop, so a five-page
 * feed cost five round trips one after the other. Every page after the first
 * is independent, so they now fan out together: the whole read is two round
 * trips regardless of corpus size.
 *
 * Deliberately takes no `AbortSignal`. The result is cached and shared, so
 * the first component to unmount must not be able to cancel a fetch that the
 * next one is still waiting on; the work finishes and warms the cache.
 */
async function readSummaryPages(): Promise<PlacementSummary> {
  const first = await fetchCompanyPlacements({ page: 1, pageSize: PAGE_SIZE });
  const pages = Math.max(1, Math.min(Math.ceil(first.totalCount / PAGE_SIZE), MAX_PAGES));
  if (pages === 1) return summarize(first.items, first.totalCount);

  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_unused, index) =>
      fetchCompanyPlacements({ page: index + 2, pageSize: PAGE_SIZE }),
    ),
  );

  // TotalCount can move between pages, so a company may legitimately appear
  // twice — `summarize` folds duplicates down to one row per company.
  return summarize(first.items.concat(...rest.map((page) => page.items)), first.totalCount);
}

function loadSummary(): Promise<PlacementSummary> {
  const hit = freshSummary();
  if (hit) return Promise.resolve(hit);

  if (!inflight) {
    inflight = readSummaryPages()
      .then((summary) => {
        cachedSummary = { value: summary, at: Date.now() };
        return summary;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

export function usePlacementSummary(): UsePlacementSummaryState & { reload: () => void } {
  // Seed from a warm cache so a second visit renders the figures on its very
  // first paint instead of flashing a loading state and correcting it.
  const [state, setState] = useState<UsePlacementSummaryState>(() => {
    const hit = freshSummary();
    return { summary: hit, loading: hit === null, error: null };
  });
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    let live = true;
    setState((prev) => ({ summary: prev.summary, loading: prev.summary === null, error: null }));

    loadSummary().then(
      (summary) => {
        if (live) setState({ summary, loading: false, error: null });
      },
      (error: unknown) => {
        if (live) setState((prev) => ({ summary: prev.summary, loading: false, error: error as Error }));
      },
    );

    // A cache-backed read is shared, so nothing here can be cancelled — only
    // whether this particular subscriber still wants the answer.
    return () => {
      live = false;
    };
  }, [retryToken]);

  const reload = useCallback(() => {
    cachedSummary = null;
    setRetryToken((token) => token + 1);
  }, []);

  return { ...state, reload };
}
