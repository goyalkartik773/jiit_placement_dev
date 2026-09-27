import type { ReactNode } from 'react';
import { Badge } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { EmptyState } from '../../common/EmptyState/EmptyState';
import { ErrorState } from '../../common/ErrorState/ErrorState';
import { Icon } from '../../common/Icon/Icon';
import { ListSkeleton } from '../../common/ListSkeleton/ListSkeleton';
import { Panel } from '../../common/Panel/Panel';
import { ACTIVITY_PAGE_SIZE } from '../../../hooks/useActivity';
import {
  activityStatusMeta,
  formatDuration,
  scriptAccent,
  scriptIcon,
  scriptLabel,
} from '../../../utils/adminScripts';
import { formatDateTime, formatRelative } from '../../../utils/format';
import type { AdminActivityItem } from '../../../types/admin.types';
import './ActivityTimeline.scss';

interface ActivityTimelineProps {
  /** The whole loaded activity list — the timeline shows its first page. */
  items: AdminActivityItem[];
  totalCount: number | null;
  loading: boolean;
  error: string | null;
  /** Id of the archived row whose output is open in the console (replay). */
  activeId: string | null;
  onReplay: (item: AdminActivityItem) => void;
  onRetry: () => void;
}

/**
 * Activity timeline: a hairline rail over the first activity page — script
 * glyph, status dot, server message and timing per run, newest at the top.
 * The Replay button opens the row's stored console output above.
 */
export function ActivityTimeline({
  items,
  totalCount,
  loading,
  error,
  activeId,
  onReplay,
  onRetry,
}: ActivityTimelineProps) {
  const shown = items.slice(0, ACTIVITY_PAGE_SIZE);
  const hidden = totalCount !== null ? Math.max(0, totalCount - shown.length) : null;
  const meta = hidden && hidden > 0 ? `${shown.length} of ${totalCount} shown` : undefined;

  let body: ReactNode;

  if (shown.length === 0 && loading) {
    body = <ListSkeleton count={3} label="Loading activity" />;
  } else if (shown.length === 0 && error) {
    body = <ErrorState title="Activity unavailable" message={error} onRetry={onRetry} />;
  } else if (shown.length === 0) {
    body = (
      <EmptyState
        title="No activity yet"
        description="Sign-ins and script runs recorded on this server appear on this timeline as soon as they happen."
      />
    );
  } else {
    body = (
      <>
        {error ? (
          <p className="timeline__error" role="alert">
            <Icon name="alert-circle" size={15} />
            <span>{error}</span>
            <Button variant="soft" size="sm" onClick={onRetry}>
              Retry
            </Button>
          </p>
        ) : null}

        <ol className="timeline">
          {shown.map((item, index) => {
            const status = activityStatusMeta(item.status);
            const when = item.finishedat ?? item.startedat ?? null;
            const active = item.id !== undefined && item.id === activeId;
            const canReplay = (item.output?.length ?? 0) > 0;
            const timing = [
              formatRelative(when) ?? (when ? formatDateTime(when) : null),
              typeof item.durationms === 'number' ? formatDuration(item.durationms) : null,
              item.username ?? null,
            ]
              .filter((part): part is string => Boolean(part))
              .join(' · ');

            return (
              <li
                className={`timeline__item${active ? ' timeline__item--active' : ''}`}
                key={item.id ?? index}
              >
                <span className="timeline__marker" aria-hidden="true">
                  <span className={`timeline__glyph timeline__glyph--${scriptAccent(item.script)}`}>
                    <Icon name={scriptIcon(item.script)} size={13} />
                  </span>
                  <span className={`timeline__dot timeline__dot--${status.tone}`} />
                </span>

                <div className="timeline__body">
                  <div className="timeline__row">
                    <span className="timeline__script">{scriptLabel(item.script)}</span>
                    <Badge tone={status.tone} className="badge--pill">
                      {status.label}
                    </Badge>
                  </div>
                  {item.message ? <p className="timeline__message">{item.message}</p> : null}
                  {timing ? (
                    <p className="timeline__timing" title={formatDateTime(when)}>
                      {timing}
                    </p>
                  ) : null}
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
      </>
    );
  }

  return (
    <Panel className="timeline-panel" icon="zap" title="Recent activity" meta={meta}>
      {body}
    </Panel>
  );
}
