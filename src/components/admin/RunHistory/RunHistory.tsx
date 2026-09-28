import type { ReactNode } from 'react';
import { Button } from '../../common/Button/Button';
import { EmptyState } from '../../common/EmptyState/EmptyState';
import { ErrorState } from '../../common/ErrorState/ErrorState';
import { Icon } from '../../common/Icon/Icon';
import { ListSkeleton } from '../../common/ListSkeleton/ListSkeleton';
import { Panel } from '../../common/Panel/Panel';
import { HistoryList } from '../HistoryList/HistoryList';
import type { AdminActivityItem } from '../../../types/admin.types';
import './RunHistory.scss';

interface RunHistoryProps {
  /** In-page anchor target of the console nav (`#history`). */
  id?: string;
  /** Runs, newest first, appended page by page by `useActivity`. */
  items: AdminActivityItem[];
  totalCount: number | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  hasMore: boolean;
  /** Id of the archived row whose output is open in a card (replay). */
  activeId: string | null;
  onReplay: (item: AdminActivityItem) => void;
  onLoadMore: () => void;
  onRetry: () => void;
}

/**
 * Run history: a full-width white panel with every stored activity row
 * (status, description, timing, operator) and a Replay button that opens
 * the row's stored console output in the matching action card.
 */
export function RunHistory({
  id,
  items,
  totalCount,
  loading,
  loadingMore,
  error,
  hasMore,
  activeId,
  onReplay,
  onLoadMore,
  onRetry,
}: RunHistoryProps) {
  const meta = totalCount !== null ? `${totalCount.toLocaleString()} runs` : undefined;

  let body: ReactNode;

  if (items.length === 0 && loading) {
    body = <ListSkeleton count={3} label="Loading run history" />;
  } else if (items.length === 0 && error) {
    body = <ErrorState title="Run history unavailable" message={error} onRetry={onRetry} />;
  } else if (items.length === 0) {
    body = (
      <EmptyState
        title="No runs yet"
        description="Script runs recorded on this server appear here with their status, counters and stored console output."
      />
    );
  } else {
    body = (
      <>
        {error ? (
          <p className="runs__error" role="alert">
            <Icon name="alert-circle" size={15} />
            <span>{error}</span>
            <Button variant="soft" size="sm" onClick={onRetry}>
              Retry
            </Button>
          </p>
        ) : null}

        <HistoryList items={items} activeId={activeId} onReplay={onReplay} />

        <div className="runs__foot">
          {hasMore ? (
            <Button variant="ghost" size="sm" loading={loadingMore} onClick={onLoadMore}>
              Load more
            </Button>
          ) : null}
          <span className="runs__count">
            {items.length.toLocaleString()} of {totalCount !== null ? totalCount.toLocaleString() : '—'} loaded
          </span>
        </div>
      </>
    );
  }

  return (
    <Panel className="runs" id={id} icon="clock" title="Run history" meta={meta}>
      {body}
    </Panel>
  );
}
