import { Badge } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Chip } from '../../common/Chip/Chip';
import { Icon } from '../../common/Icon/Icon';
import {
  activityStatusMeta,
  counterChip,
  formatDuration,
  scriptAccent,
  scriptIcon,
  scriptLabel,
} from '../../../utils/adminScripts';
import { formatDateTime, formatRelative } from '../../../utils/format';
import type { AdminActivityItem } from '../../../types/admin.types';
import './HistoryList.scss';

interface HistoryListProps {
  /** Runs, newest first (whatever page the caller loaded). */
  items: AdminActivityItem[];
  /** Id of the stored row whose output is currently open (replay). */
  activeId: string | null;
  onReplay: (item: AdminActivityItem) => void;
}

function rowKey(item: AdminActivityItem, index: number): string {
  return item.id ?? `row-${index}`;
}

/**
 * Reusable run list: one row per stored activity — category icon badge,
 * action name + status pill, the server's own description line, a mono
 * "when · duration · actor" line and a Replay button (disabled when the
 * row stored no console output). Rows divide by a hairline, never after
 * the last one. Every word on a row comes from the API.
 */
export function HistoryList({ items, activeId, onReplay }: HistoryListProps) {
  return (
    <ol className="history-list">
      {items.map((item, index) => {
        const status = activityStatusMeta(item.status);
        const chip = counterChip(item.counters);
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
        const description = Boolean(item.message) || Boolean(chip);

        return (
          <li
            className={`history-row history-row--${scriptAccent(item.script)}${
              active ? ' history-row--active' : ''
            }`}
            key={rowKey(item, index)}
          >
            <span className="history-row__icon" aria-hidden="true">
              <Icon name={scriptIcon(item.script)} size={15} />
            </span>

            <div className="history-row__body">
              <div className="history-row__top">
                <span className="history-row__name">{scriptLabel(item.script)}</span>
                <Badge tone={status.tone} dot={status.tone === 'warning'} className="badge--pill history-row__pill">
                  {status.label}
                </Badge>
              </div>

              {description ? (
                <p className="history-row__desc">
                  {item.message ? <span className="history-row__message">{item.message}</span> : null}
                  {chip ? (
                    <Chip tone="muted" title={chip.label} className="chip--mono">
                      {chip.value.toLocaleString()} {chip.label}
                    </Chip>
                  ) : null}
                </p>
              ) : null}

              {timing ? (
                <p className="history-row__meta" title={formatDateTime(when)}>
                  {timing}
                </p>
              ) : null}
            </div>

            <Button
              variant={active ? 'soft' : 'ghost'}
              size="sm"
              icon="terminal"
              className="history-row__replay"
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
  );
}
