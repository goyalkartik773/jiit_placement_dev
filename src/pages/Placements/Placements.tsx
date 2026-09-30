import { useEffect, useMemo, useState } from 'react';
import { useCompanyPlacements } from '../../hooks/useCompanyPlacements';
import { useDebounce } from '../../hooks/useDebounce';
import { Button } from '../../components/common/Button/Button';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { Icon } from '../../components/common/Icon/Icon';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { SearchField } from '../../components/common/SearchField/SearchField';
import { Pagination } from '../../components/jobs/Pagination/Pagination';
import { CompanyCard } from '../../components/placements/CompanyCard/CompanyCard';
import { BranchStats } from '../../components/placements/BranchStats/BranchStats';
import { Card } from '../../components/ui/Card/Card';
import type { CompanyRow } from '../../types/dashboard.types';
import './Placements.scss';

const DEFAULT_PAGE_SIZE = 100; // API max - one request loads the complete company list.

type SortKey = 'placed' | 'name';

/**
 * Company-wise placement page (container).
 * Summary totals are honest: they are summed over the loaded rows and only
 * labelled as global when the single 100-per-page request holds every company.
 */
export function Placements() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [searchInput, setSearchInput] = useState('');
  const [sort, setSort] = useState<SortKey>('placed');
  const [placedOnly, setPlacedOnly] = useState(false);

  const debouncedSearch = useDebounce(searchInput, 400);
  const search = debouncedSearch.trim();

  // A new search always restarts at page 1.
  useEffect(() => {
    setPage(1);
  }, [search]);

  const { data, initialLoading, refreshing, error, reload } = useCompanyPlacements(page, pageSize, search);

  // If the current page exceeds the available range, snap back to the last one.
  useEffect(() => {
    if (data && page > data.totalPages) setPage(Math.max(1, data.totalPages));
  }, [data, page]);

  const items = useMemo(() => data?.items ?? [], [data]);
  const allLoaded = data !== null && items.length === data.totalCount;

  const totals = useMemo(() => {
    const rows: CompanyRow[] = data?.items ?? [];
    return {
      placed: rows.reduce((sum, row) => sum + (row.placedstudents || 0), 0),
      withPlacements: rows.filter((row) => row.placedstudents > 0).length,
    };
  }, [data]);

  // Client-side refinement over the loaded page (server owns search + paging).
  const visibleRows = useMemo(() => {
    const rows = placedOnly ? items.filter((row) => row.placedstudents > 0) : [...items];
    if (sort === 'name') {
      rows.sort((a, b) => a.company.localeCompare(b.company));
    } else {
      rows.sort((a, b) => b.placedstudents - a.placedstudents || a.company.localeCompare(b.company));
    }
    return rows;
  }, [items, placedOnly, sort]);

  const scopeHint = allLoaded
    ? `across all ${data?.totalCount ?? 0} companies`
    : `on this page (${items.length} of ${data?.totalCount ?? 0})`;

  // A student who appears in two companies' offers is a record in both, so the
  // figure is stated as placement records rather than unique students.
  const placedHint = !data
    ? 'waiting for data'
    : allLoaded
      ? 'students placed, counted per company'
      : `students placed on this page (${items.length} of ${data.totalCount} companies)`;

  const heading = search ? `Results for "${search}"` : 'Company-wise placement';
  const countLabel = data
    ? `${data.totalCount} compan${data.totalCount === 1 ? 'y' : 'ies'} with a job posting`
    : 'Loading companies...';

  return (
    <div className="page placements-page">
      {/* ----- Page head ----- */}
      <section className="page-head">
        <div className="page-head__text">
          <p className="page-head__eyebrow">Placements - Offer students mapped to jobs</p>
          <h1 className="page-head__title">{heading}</h1>
          <p className="page-head__count" aria-live="polite">
            {countLabel}
            {refreshing ? <span className="page-head__refreshing"> Updating...</span> : null}
          </p>
        </div>
      </section>

      {/* ----- Summary strip (summed over the loaded rows only) ----- */}
      <Card as="section" className="placements-page__stats" ariaLabel="Placement summary">
        <div className="placements-page__stat">
          <span className="placements-page__stat-value placements-page__stat-value--accent">
            {data ? data.totalCount.toLocaleString() : '-'}
          </span>
          <span className="placements-page__stat-label">Companies</span>
          <span className="placements-page__stat-hint">with at least one job</span>
        </div>
        <div className="placements-page__stat">
          <span className="placements-page__stat-value placements-page__stat-value--green">
            {data ? totals.placed.toLocaleString() : '-'}
          </span>
          <span className="placements-page__stat-label">Placement records</span>
          <span className="placements-page__stat-hint">{placedHint}</span>
        </div>
        <div className="placements-page__stat">
          <span className="placements-page__stat-value">
            {data ? totals.withPlacements.toLocaleString() : '-'}
          </span>
          <span className="placements-page__stat-label">Companies with placements</span>
          <span className="placements-page__stat-hint">{data ? scopeHint : 'waiting for data'}</span>
        </div>
      </Card>

      {/* ----- Branch-wise statistics (batch 2026-27) ---------------------- */}
      <BranchStats />

      {/* ----- Toolbar ----- */}
      {/* The company list is the H1's own subject; this sr-only level-2 keeps
          the outline correct now that a second H2 (branch stats) precedes it. */}
      <h2 className="sr-only">Companies with a job posting</h2>
      <section className="placements-page__toolbar" aria-label="Search and sort companies">
        <SearchField
          value={searchInput}
          onChange={setSearchInput}
          label="Search companies by name"
          placeholder="Search company name..."
          id="placements-search"
        />

        <div className="placements-page__segmented" role="group" aria-label="Filter companies">
          <button
            type="button"
            className="placements-page__segment"
            aria-pressed={placedOnly}
            onClick={() => setPlacedOnly((value) => !value)}
          >
            <Icon name="users" size={14} />
            With placements
          </button>
          <button
            type="button"
            className="placements-page__segment"
            aria-pressed={!placedOnly}
            onClick={() => setPlacedOnly(false)}
          >
            All companies
          </button>
        </div>

        <label className="placements-page__select">
          <span>
            <Icon name="sort" size={14} />
            Sort
          </span>
          <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
            <option value="placed">Placed count</option>
            <option value="name">Company A-Z</option>
          </select>
        </label>
      </section>

      {!allLoaded && data ? (
        <p className="placements-page__hint">
          <Icon name="info" size={14} />
          Showing {items.length} of {data.totalCount} companies - the totals and the sort cover this page only.
          Raise "Per page" to {DEFAULT_PAGE_SIZE} to load every company at once.
        </p>
      ) : null}

      {/* ----- Result states ----- */}
      {error && data ? (
        <p className="placements-page__banner" role="alert">
          <span>Refresh failed - showing the previously loaded companies. {error.message}</span>
          <Button variant="soft" size="sm" icon="refresh" onClick={reload}>
            Retry
          </Button>
        </p>
      ) : null}

      {error && !data ? (
        <ErrorState title="Could not load companies" message={error.message} onRetry={reload} />
      ) : initialLoading ? (
        <ListSkeleton count={5} label="Loading companies" />
      ) : visibleRows.length === 0 ? (
        placedOnly ? (
          <EmptyState
            title="No companies with placements"
            description="None of the companies on this page have a recorded offer student yet."
            action={
              <Button variant="primary" icon="users" onClick={() => setPlacedOnly(false)}>
                Show every company
              </Button>
            }
          />
        ) : search ? (
          <EmptyState
            title="No matching companies"
            description={`Nothing matched "${search}". Try a shorter company name.`}
            action={
              <Button variant="primary" icon="x" onClick={() => setSearchInput('')}>
                Clear search
              </Button>
            }
          />
        ) : (
          <EmptyState title="No companies found" description="Companies appear here as soon as a job is posted." />
        )
      ) : (
        <div className={`placements-page__list${refreshing ? ' is-refreshing' : ''}`} aria-busy={refreshing || undefined}>
          {visibleRows.map((row) => (
            <CompanyCard key={row.company} row={row} />
          ))}
        </div>
      )}

      {data && data.totalCount > 0 ? (
        <Pagination
          page={page}
          totalPages={data.totalPages}
          pageSize={data.pageSize}
          totalCount={data.totalCount}
          itemCount={items.length}
          disabled={refreshing}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
        />
      ) : null}
    </div>
  );
}
