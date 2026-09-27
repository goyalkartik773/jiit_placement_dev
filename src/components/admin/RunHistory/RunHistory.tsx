import type { ReactNode } from 'react';
import { Badge } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Chip } from '../../common/Chip/Chip';
import { EmptyState } from '../../common/EmptyState/EmptyState';
import { ErrorState } from '../../common/ErrorState/ErrorState';
import { Icon } from '../../common/Icon/Icon';
import { ListSkeleton } from '../../common/ListSkeleton/ListSkeleton';
import { Panel } from '../../common/Panel/Panel';
import { activityStatusMeta, counterChip, formatDuration, scriptIcon, scriptLabel } from '../../../utils/adminScripts';
import { formatDateTime, formatRelative } from '../../../utils/format';
import type { AdminActivityItem } from '../../../types/admin.types';
import './RunHistory.scss';

interface RunHistoryProps {
  /** Runs, newest first, appended page by page by `useActivity`. */
  items: AdminActivityItem[];
  totalCount: number | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  hasMore: boolean;
  /** Id of the archived row whose output is open in the console (replay). */
  activeId: string | null;
  onReplay: (item: AdminActivityItem) => void;
  onLoadMore: () => void;
  onRetry: () => void;
}

function rowKey(item: AdminActivityItem, index: number): string {
  return item.id ?? `row-${index}`;
}

/**
 * Run history: every stored activity row with its status, headline counter,
 * timing and operator — plus a Replay button that opens the row's stored
 * console output (disabled when the row has none).
 */
export function RunHistory({
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

        <ol className="runs__list">
          {items.map((item, index) => {
            const status = activityStatusMeta(item.status);
            const chip = counterChip(item.counters);
            const when = item.finishedat ?? item.startedat ?? null;
            const active = item.id !== undefined && item.id === activeId;
            const canReplay = (item.output?.length ?? 0) > 0;

            return (
              <li className={`runs__row${active ? ' runs__row--active' : ''}`} key={rowKey(item, index)}>
                <span className="runs__icon" aria-hidden="true">
                  <Icon name={scriptIcon(item.script)} size={15} />
                </span>

                <div className="runs__body">
                  <div className="runs__top">
                    <span className="runs__script">{scriptLabel(item.script)}</span>
                    <Badge tone={status.tone} dot>
                      {status.label}
                    </Badge>
                    {chip ? (
                      <Chip tone="muted" title={chip.label}>
                        {chip.value.toLocaleString()} {chip.label}
                      </Chip>
                    ) : null}
                  </div>

                  {item.message ? <p className="runs__message">{item.message}</p> : null}

                  <p className="runs__meta">
                    <span title={formatDateTime(when)}>{formatRelative(when) ?? formatDateTime(when)}</span>
                    {typeof item.durationms === 'number' ? (
                      <>
                        <span aria-hidden="true">·</span>
                        <span>{formatDuration(item.durationms)}</span>
                      </>
                    ) : null}
                    {item.username ? (
                      <>
                        <span aria-hidden="true">·</span>
                        <span>{item.username}</span>
                      </>
                    ) : null}
                  </p>
                </div>

                <Button
                  variant={active ? 'soft' : 'ghost'}
                  size="sm"
                  icon="terminal"
                  disabled={!canReplay}
                  title={canReplay ? 'Open this run’s stored output in the console' : 'No stored output for this run'}
                  ariaLabel={`Replay output of ${scriptLabel(item.script)}`}
                  onClick={() => onReplay(item)}
                >
                  Replay
                </Button>
              </li>
            );
          })}
        </ol>

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
    <Panel className="runs" icon="clock" title="Run history" meta={meta}>
      {body}
    </Panel>
  );
}
