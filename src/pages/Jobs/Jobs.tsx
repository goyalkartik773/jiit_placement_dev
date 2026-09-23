import { useEffect, useMemo, useState } from 'react';
import { useDebounce } from '../../hooks/useDebounce';
import { useJobs } from '../../hooks/useJobs';
import { Button } from '../../components/common/Button/Button';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { JobList } from '../../components/jobs/JobList/JobList';
import { JobListSkeleton } from '../../components/jobs/JobList/JobListSkeleton';
import { JobsToolbar } from '../../components/jobs/JobsToolbar/JobsToolbar';
import { Pagination } from '../../components/jobs/Pagination/Pagination';
import { TierLegend } from '../../components/jobs/TierLegend/TierLegend';
import { DEFAULT_FILTERS, applyFilters, extractFilterOptions, hasActiveFilters, type JobFilters } from '../../utils/jobList';
import './Jobs.scss';

const DEFAULT_PAGE_SIZE = 100; // API max — loads the full current dataset in one call.

/**
 * Jobs listing page (container).
 * Owns query state only; fetching lives in useJobs → jobService → apiClient.
 */
export function Jobs() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [searchInput, setSearchInput] = useState('');
  const [filters, setFilters] = useState<JobFilters>(DEFAULT_FILTERS);

  const debouncedSearch = useDebounce(searchInput, 400);
  const search = debouncedSearch.trim();

  // A new search always restarts at page 1.
  useEffect(() => {
    setPage(1);
  }, [search]);

  const { data, initialLoading, refreshing, error, reload } = useJobs(page, pageSize, search);

  // If the current page exceeds the available range (e.g. after shrinking the
  // page size), snap back to the last real page.
  useEffect(() => {
    if (data && page > data.totalPages) setPage(Math.max(1, data.totalPages));
  }, [data, page]);

  const items = useMemo(() => data?.items ?? [], [data]);

  // Refinement (location/status/category/sort) runs client-side and only over
  // the COMPLETE result set, so counts never lie. The backend only supports
  // server-side search + company + pagination.
  const refineAvailable = Boolean(data && !error && items.length === data.totalCount);

  const options = useMemo(() => extractFilterOptions(items), [items]);
  const filtersActive = hasActiveFilters(filters);

  const visibleJobs = useMemo(
    () => (refineAvailable ? applyFilters(items, filters) : items),
    [refineAvailable, items, filters],
  );

  const updateFilters = (patch: Partial<JobFilters>) => setFilters((current) => ({ ...current, ...patch }));
  const clearSearch = () => setSearchInput('');

  const heading = search ? `Results for “${search}”` : 'Posted opportunities';
  const countLabel = data
    ? refineAvailable && filtersActive
      ? `${visibleJobs.length} of ${data.totalCount} job${data.totalCount === 1 ? '' : 's'}`
      : `${data.totalCount} job${data.totalCount === 1 ? '' : 's'}`
    : 'Loading jobs…';

  return (
    <div className="page jobs-page">
      {/* ----- Page head ----- */}
      <section className="page-head">
        <div className="page-head__text">
          <p className="page-head__eyebrow">Placement season · Live data</p>
          <h1 className="page-head__title">{heading}</h1>
          <p className="page-head__count" aria-live="polite">
            {countLabel}
            {refreshing ? <span className="page-head__refreshing"> Updating…</span> : null}
          </p>
        </div>
      </section>

      <JobsToolbar
        searchInput={searchInput}
        onSearchChange={setSearchInput}
        filters={filters}
        onFiltersChange={updateFilters}
        onClearFilters={() => setFilters(DEFAULT_FILTERS)}
        filtersActive={filtersActive}
        refineAvailable={refineAvailable}
        options={options}
      />

      {/* Fixed color-coding key — teaches tiers/criteria before the grid */}
      <TierLegend />

      {/* ----- Result states ----- */}
      {error && !data ? (
        <ErrorState title="Could not load jobs" message={error.message} onRetry={reload} />
      ) : initialLoading ? (
        <JobListSkeleton count={6} />
      ) : error ? (
        <div className="jobs-page__banner" role="alert">
          <span>Refresh failed — showing the previously loaded jobs. {error.message}</span>
          <Button variant="soft" size="sm" icon="refresh" onClick={reload}>
            Retry
          </Button>
          <JobList jobs={visibleJobs} refreshing />
        </div>
      ) : items.length === 0 ? (
        search ? (
          <EmptyState
            title="No matching jobs"
            description={`Nothing matched “${search}”. Try a different company or role.`}
            action={
              <Button variant="primary" icon="x" onClick={clearSearch}>
                Clear search
              </Button>
            }
          />
        ) : (
          <EmptyState title="No jobs posted yet" description="Jobs will appear here as soon as they are published to the API." />
        )
      ) : visibleJobs.length === 0 ? (
        <EmptyState
          title="No jobs match these filters"
          description="Adjust or clear the refinement filters to see more results."
          action={
            <Button variant="primary" icon="refresh" onClick={() => setFilters(DEFAULT_FILTERS)}>
              Clear filters
            </Button>
          }
        />
      ) : (
        <JobList jobs={visibleJobs} refreshing={refreshing} />
      )}

      {data && data.totalCount > 0 && !error ? (
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
