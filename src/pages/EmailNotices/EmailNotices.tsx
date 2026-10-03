import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useDebounce } from '../../hooks/useDebounce';
import { useEmailNoticeDetail } from '../../hooks/useEmailNoticeDetail';
import { useEmailNotices } from '../../hooks/useEmailNotices';
import { Button } from '../../components/common/Button/Button';
import { EmptyState } from '../../components/common/EmptyState/EmptyState';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { Icon } from '../../components/common/Icon/Icon';
import { ListSkeleton } from '../../components/common/ListSkeleton/ListSkeleton';
import { Skeleton } from '../../components/common/Skeleton/Skeleton';
import { SearchField } from '../../components/common/SearchField/SearchField';
import { Pagination } from '../../components/jobs/Pagination/Pagination';
import { EmailNoticeDetail } from '../../components/notices/EmailNoticeDetail/EmailNoticeDetail';
import {
  classificationCueOf,
  classificationLabelOf,
  NoticeRow,
  type NoticeMarks,
} from '../../components/notices/NoticeRow/NoticeRow';
import './EmailNotices.scss';

const DEFAULT_PAGE_SIZE = 20;

/** Empty reading pane. The brief's exact line - it is the point of the layout. */
const PANE_EMPTY_TITLE = 'Select a placement notice…';

/** Loading state of the reading pane, shaped like the pane it replaces. */
function ReadingSkeleton() {
  return (
    <div className="ews__skel" role="status">
      <span className="sr-only">Loading this notice…</span>
      <Skeleton width="full" height="md" shape="rect" />
      <Skeleton width="full" height="lg" shape="rect" />
      <Skeleton width="sm" height="xs" shape="pill" />
      <Skeleton width="full" height="lg" shape="rect" />
      <Skeleton width="full" height="lg" shape="rect" />
      <Skeleton width="full" height="md" shape="rect" />
    </div>
  );
}

/**
 * Email notices — a three-column master/detail workspace.
 *
 * Layout, left to right: a 64px classification rail, the notice list, and the
 * reading pane. Below 1280px the last two cannot both hold a usable measure
 * (the pane would fall under ~350px), so the workspace becomes a toggle: one
 * pane at a time, with the row click serving as "open" and the action bar's
 * Back serving as "return".
 *
 * Two things deliberately do not live here:
 *
 *   - SELECTION IS THE URL. `?notice=<id>` is the source of truth, so a
 *     notice can be linked to, survives a reload, works when deep-linked from
 *     outside the list (the id is not validated against the current page —
 *     the API takes it directly), and makes "Copy link" in the action bar a
 *     real action rather than a decorative one.
 *
 *   - TRIAGE IS SESSION-LOCAL. Star / Archive / Mark unread are backed by
 *     three Sets in this component and nothing else: there is no endpoint for
 *     them in `noticeService`, and inventing persistence would be claiming a
 *     durability the app does not have. Archiving is therefore always
 *     reversible from a control that is on screen the moment anything is
 *     archived — no notice can disappear without a visible way back.
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

  // ----- selection, kept in the query string ---------------------------------
  const [params, setParams] = useSearchParams();
  const selectedId = params.get('notice');

  const selectNotice = useCallback(
    (id: string) => {
      const next = new URLSearchParams(params);
      next.set('notice', id);
      // replace, not push: stepping through a list should not bury the Back
      // button under one history entry per row.
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const clearSelection = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete('notice');
    setParams(next, { replace: true });
  }, [params, setParams]);

  const { detail, loading: detailLoading, error: detailError, reload: reloadDetail } = useEmailNoticeDetail(selectedId);

  // ----- session-local triage ------------------------------------------------
  const [starred, setStarred] = useState<ReadonlySet<string>>(() => new Set());
  const [archived, setArchived] = useState<ReadonlySet<string>>(() => new Set());
  const [unread, setUnread] = useState<ReadonlySet<string>>(() => new Set());
  const [showArchived, setShowArchived] = useState(false);

  const toggleSet = useCallback((setter: Dispatch<SetStateAction<ReadonlySet<string>>>, id: string) => {
    setter((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const restoreAll = useCallback(() => {
    setArchived(new Set());
    setShowArchived(false);
  }, []);

  /** One place that decides what a given id is marked with, for row and pane. */
  const marksFor = useCallback(
    (id: string): NoticeMarks => ({
      starred: starred.has(id),
      unread: unread.has(id),
      archived: archived.has(id),
    }),
    [starred, unread, archived],
  );

  const items = useMemo(() => data?.items ?? [], [data]);
  const facets = useMemo(() => data?.facets ?? [], [data]);
  const typeLabel = type ? classificationLabelOf(type) : null;

  // Facets ignore the active `type`, so their sum is the honest "All" count
  // for the current search (the filtered totalCount would understate it).
  const allCount = useMemo(
    () => (facets.length > 0 ? facets.reduce((sum, facet) => sum + (facet.count || 0), 0) : data?.totalCount ?? 0),
    [facets, data],
  );

  // Archiving filters the list, never the data: the same page of notices is
  // shown through a different predicate, so paging and counts stay honest.
  const viewingArchived = showArchived && archived.size > 0;
  const visible = useMemo(
    () => items.filter((notice) => (viewingArchived ? archived.has(notice.id) : !archived.has(notice.id))),
    [items, archived, viewingArchived],
  );

  const heading = search ? `Results for "${search}"` : 'Email notices';
  const countLabel = data
    ? `${data.totalCount} notice${data.totalCount === 1 ? '' : 's'}${typeLabel ? ` - ${typeLabel} only` : ''}`
    : 'Loading email notices...';

  const hasActiveFilter = Boolean(type || search);

  const renderRows = () => {
    if (error && !data) return <ErrorState title="Could not load email notices" message={error.message} onRetry={reload} />;
    if (initialLoading) return <ListSkeleton count={5} label="Loading email notices" />;
    if (items.length === 0) {
      return hasActiveFilter ? (
        <EmptyState
          title="No matching notices"
          description={`Nothing matched${search ? ` "${search}"` : ''}${typeLabel ? ` in ${typeLabel}` : ''}.`}
          action={
            <Button variant="primary" icon="refresh" onClick={() => { setSearchInput(''); setType(''); }}>
              Clear filters
            </Button>
          }
        />
      ) : (
        <EmptyState title="No email notices yet" description="Parsed placement emails will appear here." />
      );
    }
    if (visible.length === 0) {
      return viewingArchived ? (
        <EmptyState title="Nothing archived on this page" description="Archived notices from other pages are still archived." />
      ) : (
        <EmptyState
          title="Everything on this page is archived"
          description="Restore them to see the notices again."
          action={<Button variant="primary" icon="inbox" onClick={restoreAll}>Restore all</Button>}
        />
      );
    }

    return (
      <ul className="ews__rows">
        {visible.map((notice) => (
          <NoticeRow
            key={notice.id}
            notice={notice}
            selected={notice.id === selectedId}
            marks={marksFor(notice.id)}
            onSelect={selectNotice}
          />
        ))}
      </ul>
    );
  };

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
        Congratulation and final-offer emails are excluded - that data lives in{' '}
        <Link className="email-notices-page__intro-link" to="/placements">
          Company-Wise Placement
        </Link>
        .
      </p>

      {error && data ? (
        <p className="email-notices-page__banner" role="alert">
          <span>Refresh failed - showing the previously loaded notices. {error.message}</span>
          <Button variant="soft" size="sm" icon="refresh" onClick={reload}>
            Retry
          </Button>
        </p>
      ) : null}

      <div
        className="ews"
        data-pane={selectedId ? 'detail' : 'list'}
        // Busy during a refetch AND on first load. `refreshing` is only set
        // once data exists (`initialLoading: prev.data === null` in the hook),
        // so the original expression left `aria-busy` off for the one state
        // where the whole list is a skeleton.
        aria-busy={refreshing || initialLoading || undefined}
      >
        {/* ----- 64px classification rail ----- */}
        <nav className="ews__rail" aria-label="Notices by classification">
          <button
            type="button"
            className={`ews__rail-item${type === '' ? ' is-on' : ''}`}
            aria-pressed={type === ''}
            title="All classifications"
            onClick={() => setType('')}
          >
            <Icon name="inbox" size={18} />
            <span className="ews__rail-count">{data ? allCount : null}</span>
            <span className="sr-only">All classifications</span>
          </button>

          {facets.map((facet) => (
            <button
              key={facet.classification}
              type="button"
              className={`ews__rail-item${type === facet.classification ? ' is-on' : ''}`}
              aria-pressed={type === facet.classification}
              title={`Filter by ${classificationLabelOf(facet.classification)}`}
              onClick={() => setType((current) => (current === facet.classification ? '' : facet.classification))}
            >
              <Icon name={classificationCueOf(facet.classification).icon} size={18} />
              <span className="ews__rail-count">{facet.count}</span>
              <span className="sr-only">{classificationLabelOf(facet.classification)}</span>
            </button>
          ))}
        </nav>

        {/* ----- notice list ----- */}
        <section className="ews__list" aria-label="Notice list" aria-busy={refreshing || initialLoading || undefined}>
          <div className="ews__list-head">
            <SearchField
              value={searchInput}
              onChange={setSearchInput}
              label="Search email notices"
              placeholder="Search subject, company or sender..."
              id="email-notices-search"
            />
            {hasActiveFilter ? (
              <Button variant="ghost" size="sm" icon="x" onClick={() => { setSearchInput(''); setType(''); }}>
                Clear
              </Button>
            ) : null}
          </div>

          {archived.size > 0 ? (
            <div className="ews__archive-bar">
              <button
                type="button"
                className={`ews__archive-chip${viewingArchived ? ' is-on' : ''}`}
                aria-pressed={viewingArchived}
                onClick={() => setShowArchived((on) => !on)}
              >
                <Icon name="archive" size={13} />
                {viewingArchived ? `Showing ${archived.size} archived` : `Archived (${archived.size})`}
              </button>
              {viewingArchived ? (
                <Button variant="ghost" size="sm" onClick={restoreAll}>
                  Restore all
                </Button>
              ) : null}
            </div>
          ) : null}

          <div className="ews__list-scroll">{renderRows()}</div>

          {data && data.totalCount > 0 ? (
            <div className="ews__list-foot">
              <Pagination
                page={page}
                totalPages={data.totalPages}
                pageSize={data.pageSize}
                totalCount={data.totalCount}
                itemCount={items.length}
                disabled={refreshing}
                noun="notice"
                onPageChange={setPage}
                onPageSizeChange={(size) => {
                  setPageSize(size);
                  setPage(1);
                }}
              />
            </div>
          ) : null}
        </section>

        {/* ----- reading pane ----- */}
        <section className="ews__detail" aria-label="Reading pane">
          {detailLoading ? (
            <ReadingSkeleton />
          ) : detailError && !detail ? (
            <ErrorState title="Could not load this email" message={detailError.message} onRetry={reloadDetail} />
          ) : detail ? (
            <EmailNoticeDetail
              detail={detail}
              onBack={clearSelection}
              marks={marksFor(detail.id)}
              onToggleStar={() => toggleSet(setStarred, detail.id)}
              onToggleArchive={() => toggleSet(setArchived, detail.id)}
              onToggleUnread={() => toggleSet(setUnread, detail.id)}
            />
          ) : (
            <div className="ews__empty">
              <EmptyState title={PANE_EMPTY_TITLE} description="Pick a notice on the left to read it here." />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
