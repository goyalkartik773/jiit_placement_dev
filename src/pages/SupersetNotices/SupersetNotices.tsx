import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDebounce } from '../../hooks/useDebounce';
import { useSupersetNotices } from '../../hooks/useSupersetNotices';
import { Button } from '../../components/common/Button/Button';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { SearchField } from '../../components/common/SearchField/SearchField';
import { Pagination } from '../../components/jobs/Pagination/Pagination';
import { SupersetNoticeCard } from '../../components/notices/SupersetNoticeCard/SupersetNoticeCard';
import './SupersetNotices.scss';

const DEFAULT_PAGE_SIZE = 20;

/**
 * Superset notices page (container). Fetching lives in useSupersetNotices ->
 * noticeService -> apiClient; the cards expand the full body on demand.
 */
export function SupersetNotices() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [searchInput, setSearchInput] = useState('');

  const debouncedSearch = useDebounce(searchInput, 400);
  const search = debouncedSearch.trim();

  // A new search always restarts at page 1.
  useEffect(() => {
    setPage(1);
  }, [search]);

  const { data, initialLoading, refreshing, error, reload } = useSupersetNotices(page, pageSize, search);

  // If the current page exceeds the available range, snap back to the last one.
  useEffect(() => {
    if (data && page > data.totalPages) setPage(Math.max(1, data.totalPages));
  }, [data, page]);

  const items = useMemo(() => data?.items ?? [], [data]);

  const heading = search ? `Results for "${search}"` : 'Superset notices';
  const countLabel = data
    ? `${data.totalCount} notice${data.totalCount === 1 ? '' : 's'} synced from the portal`
    : 'Loading Superset notices...';

  return (
    <div className="page superset-notices-page">
      {/* ----- Page head ----- */}
      <section className="page-head">
        <div className="page-head__text">
          <p className="page-head__eyebrow">Notices - Synced from the Superset portal</p>
          <h1 className="page-head__title">{heading}</h1>
          <p className="page-head__count" aria-live="polite">
            {countLabel}
            {refreshing ? <span className="page-head__refreshing"> Updating...</span> : null}
          </p>
        </div>
      </section>

      <p className="superset-notices-page__intro">
        Announcements published on the Superset job portal, synced as-is. The job listings themselves stay
        in <Link className="superset-notices-page__intro-link" to="/">Active Job Listing</Link>.
      </p>

      {/* ----- Search ----- */}
      <section className="superset-notices-page__toolbar" aria-label="Search Superset notices">
        <SearchField
          value={searchInput}
          onChange={setSearchInput}
          label="Search Superset notices"
          placeholder="Search title or author..."
          id="superset-notices-search"
        />
        {search ? (
          <Button variant="ghost" size="sm" icon="x" onClick={() => setSearchInput('')}>
            Clear
          </Button>
        ) : null}
      </section>

      {/* ----- Result states ----- */}
      {error && data ? (
        <p className="superset-notices-page__banner" role="alert">
          <span>Refresh failed - showing the previously loaded notices. {error.message}</span>
          <Button variant="soft" size="sm" icon="refresh" onClick={reload}>
            Retry
          </Button>
        </p>
      ) : null}

      {error && !data ? (
        <ErrorState title="Could not load notices" message={error.message} onRetry={reload} />
      ) : initialLoading ? (
        <ListSkeleton count={4} label="Loading Superset notices" />
      ) : items.length === 0 ? (
        search ? (
          <EmptyState
            title="No matching notices"
            description={`Nothing matched "${search}". Try an author or a shorter title.`}
            action={
              <Button variant="primary" icon="x" onClick={() => setSearchInput('')}>
                Clear search
              </Button>
            }
          />
        ) : (
          <EmptyState title="No notices yet" description="Portal announcements will appear here once they are synced." />
        )
      ) : (
        <div className={`superset-notices-page__list${refreshing ? ' is-refreshing' : ''}`} aria-busy={refreshing || undefined}>
          {items.map((notice) => (
            <SupersetNoticeCard key={notice.id} notice={notice} />
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
