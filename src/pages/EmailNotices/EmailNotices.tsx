import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDebounce } from '../../hooks/useDebounce';
import { useEmailNotices } from '../../hooks/useEmailNotices';
import { Button } from '../../components/common/Button/Button';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { SearchField } from '../../components/common/SearchField/SearchField';
import { Pagination } from '../../components/jobs/Pagination/Pagination';
import { classificationLabelOf, EmailNoticeCard } from '../../components/notices/EmailNoticeCard/EmailNoticeCard';
import './EmailNotices.scss';

const DEFAULT_PAGE_SIZE = 20;

/**
 * Email notices page (container).
 * `type` is sent uppercase to the API; the facet chips come back for the
 * current search and ignore the active type, exactly as the backend does.
 */
export function EmailNotices() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [searchInput, setSearchInput] = useState('');
  const [type, setType] = useState('');

  const debouncedSearch = useDebounce(searchInput, 400);
  const search = debouncedSearch.trim();

  // A new search or a new classification always restarts at page 1.
  useEffect(() => {
    setPage(1);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [type]);

  const { data, initialLoading, refreshing, error, reload } = useEmailNotices(page, pageSize, search, type);

  // If the current page exceeds the available range, snap back to the last one.
  useEffect(() => {
    if (data && page > data.totalPages) setPage(Math.max(1, data.totalPages));
  }, [data, page]);

  const items = useMemo(() => data?.items ?? [], [data]);
  const facets = useMemo(() => data?.facets ?? [], [data]);
  const typeLabel = type ? classificationLabelOf(type) : null;

  // Facets ignore the active `type`, so their sum is the honest "All" count
  // for the current search (the filtered totalCount would understate it).
  const allCount = useMemo(
    () => (facets.length > 0 ? facets.reduce((sum, facet) => sum + (facet.count || 0), 0) : data?.totalCount ?? 0),
    [facets, data],
  );

  const heading = search ? `Results for "${search}"` : 'Email notices';
  const countLabel = data
    ? `${data.totalCount} notice${data.totalCount === 1 ? '' : 's'}${typeLabel ? ` - ${typeLabel} only` : ''}`
    : 'Loading email notices...';

  return (
    <div className="page email-notices-page">
      {/* ----- Page head ----- */}
      <section className="page-head">
        <div className="page-head__text">
          <p className="page-head__eyebrow">Notices - Parsed from placement emails</p>
          <h1 className="page-head__title">{heading}</h1>
          <p className="page-head__count" aria-live="polite">
            {countLabel}
            {refreshing ? <span className="page-head__refreshing"> Updating...</span> : null}
          </p>
        </div>
      </section>

      <p className="email-notices-page__intro">
        Every notice below is parsed from a placement email in the mailbox. Congratulation and final-offer
        emails are intentionally left out - that data lives in{' '}
        <Link className="email-notices-page__intro-link" to="/placements">
          Company-Wise Placement
        </Link>
        .
      </p>

      {/* ----- Classification facets ----- */}
      <section className="email-notices-page__facets" aria-label="Filter notices by classification">
        <button
          type="button"
          className={`email-notices-page__facet${type === '' ? ' is-on' : ''}`}
          aria-pressed={type === ''}
          onClick={() => setType('')}
        >
          All
          <span className="email-notices-page__facet-count">{data ? allCount : null}</span>
        </button>

        {facets.map((facet) => (
          <button
            key={facet.classification}
            type="button"
            className={`email-notices-page__facet${type === facet.classification ? ' is-on' : ''}`}
            aria-pressed={type === facet.classification}
            title={`Filter by ${classificationLabelOf(facet.classification)}`}
            onClick={() => setType((current) => (current === facet.classification ? '' : facet.classification))}
          >
            {classificationLabelOf(facet.classification)}
            <span className="email-notices-page__facet-count">{facet.count}</span>
          </button>
        ))}
      </section>

      {/* ----- Search ----- */}
      <section className="email-notices-page__toolbar" aria-label="Search email notices">
        <SearchField
          value={searchInput}
          onChange={setSearchInput}
          label="Search email notices"
          placeholder="Search subject, company or sender..."
          id="email-notices-search"
        />
        {type || search ? (
          <Button variant="ghost" size="sm" icon="x" onClick={() => { setSearchInput(''); setType(''); }}>
            Clear
          </Button>
        ) : null}
      </section>

      {/* ----- Result states ----- */}
      {error && data ? (
        <p className="email-notices-page__banner" role="alert">
          <span>Refresh failed - showing the previously loaded notices. {error.message}</span>
          <Button variant="soft" size="sm" icon="refresh" onClick={reload}>
            Retry
          </Button>
        </p>
      ) : null}

      {error && !data ? (
        <ErrorState title="Could not load email notices" message={error.message} onRetry={reload} />
      ) : initialLoading ? (
        <ListSkeleton count={4} label="Loading email notices" />
      ) : items.length === 0 ? (
        search || type ? (
          <EmptyState
            title="No matching notices"
            description={`Nothing matched${search ? ` "${search}"` : ''}${typeLabel ? ` in ${typeLabel}` : ''}.`}
            action={
              <Button
                variant="primary"
                icon="refresh"
                onClick={() => {
                  setSearchInput('');
                  setType('');
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState title="No email notices yet" description="Parsed placement emails will appear here." />
        )
      ) : (
        <div className={`email-notices-page__list${refreshing ? ' is-refreshing' : ''}`} aria-busy={refreshing || undefined}>
          {items.map((notice) => (
            <EmailNoticeCard key={notice.id} notice={notice} />
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
