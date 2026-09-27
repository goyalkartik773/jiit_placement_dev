import { useCallback, useState } from 'react';
import { Badge } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
import { Panel } from '../../common/Panel/Panel';
import { useToast } from '../../common/Toast/Toast';
import { ApiError, isAbortError } from '../../../services/apiClient';
import { syncOfferStudents } from '../../../services/adminService';
import type { AdminOfferSyncResponse } from '../../../types/admin.types';
import { formatDateTime } from '../../../utils/format';
import './OfferSyncPanel.scss';

interface OfferSyncPanelProps {
  /** The Admin page's existing session-expiry handler, called on a 401. */
  onUnauthorized: () => void;
}

type CounterKey =
  | 'jobsMatched'
  | 'studentsMapped'
  | 'mappingsInserted'
  | 'duplicatesSkipped'
  | 'companiesSkipped'
  | 'totalMappings';

/** The counters shown after a run - every value comes straight from the API. */
const COUNTERS: { key: CounterKey; label: string }[] = [
  { key: 'jobsMatched', label: 'Jobs matched' },
  { key: 'studentsMapped', label: 'Students mapped' },
  { key: 'mappingsInserted', label: 'Mappings inserted' },
  { key: 'duplicatesSkipped', label: 'Duplicates skipped' },
  { key: 'companiesSkipped', label: 'Companies skipped' },
  { key: 'totalMappings', label: 'Total mappings' },
];

/**
 * Admin card for POST /api/admin/jobs/sync-offer-students: one action plus
 * the counters of the last run. Nothing is pre-filled - the hint replaces the
 * grid until the API has actually returned a result.
 */
export function OfferSyncPanel({ onUnauthorized }: OfferSyncPanelProps) {
  const { showToast } = useToast();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AdminOfferSyncResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (): Promise<void> => {
    setRunning(true);
    setError(null);

    try {
      const response = await syncOfferStudents();
      setResult(response);
      showToast(response.message || 'Offer students matched onto the job list.', 'success');
    } catch (caught: unknown) {
      if (isAbortError(caught)) return;
      if (caught instanceof ApiError && caught.httpStatus === 401) {
        onUnauthorized();
        return;
      }
      const message = caught instanceof Error ? caught.message : 'The offer-student sync could not be completed.';
      setError(message);
      showToast(message, 'error');
    } finally {
      setRunning(false);
    }
  }, [onUnauthorized, showToast]);

  const summary = result
    ? [
        `${result.jobsMatched.toLocaleString()} jobs matched`,
        `${result.studentsMapped.toLocaleString()} students mapped`,
        `${result.totalMappings.toLocaleString()} mappings on record`,
      ].join(', ')
    : null;

  return (
    <Panel
      className="offer-sync-panel"
      icon="users"
      title="Sync jobs with offered students"
      meta={
        result ? (
          <Badge tone="success">{formatDateTime(result.lastRunAt)}</Badge>
        ) : (
          <Badge tone="neutral">Not run yet</Badge>
        )
      }
    >
      <p className="offer-sync-panel__explain">
        Matches the offer-student data parsed from congratulation emails onto the jobs already in the system.
        Companies that are not present in the job listing are skipped.
      </p>

      <div className="offer-sync-panel__actions">
        <Button variant="primary" icon="zap" loading={running} onClick={() => void run()}>
          Sync jobs with offer students
        </Button>
        {summary ? <span className="offer-sync-panel__summary">{summary}.</span> : null}
      </div>

      {error ? (
        <p className="offer-sync-panel__error" role="alert">
          <Icon name="alert-circle" size={15} />
          <span>{error}</span>
        </p>
      ) : null}

      {result ? (
        <div className="offer-sync-panel__stats" aria-live="polite">
          {COUNTERS.map((counter) => (
            <div className="offer-sync-panel__stat" key={counter.key}>
              <span className="offer-sync-panel__stat-label">{counter.label}</span>
              <span className="offer-sync-panel__stat-value">{result[counter.key].toLocaleString()}</span>
            </div>
          ))}
          <div className="offer-sync-panel__stat">
            <span className="offer-sync-panel__stat-label">Last run</span>
            <span className="offer-sync-panel__stat-value offer-sync-panel__stat-value--time">
              {formatDateTime(result.lastRunAt)}
            </span>
          </div>
          <div className="offer-sync-panel__stat">
            <span className="offer-sync-panel__stat-label">Jobs without placements</span>
            <span className="offer-sync-panel__stat-value">{result.jobsWithoutPlacements.toLocaleString()}</span>
          </div>
        </div>
      ) : (
        <p className="offer-sync-panel__hint">
          <Icon name="info" size={15} />
          No sync has run in this session yet. Run it once and the real counters appear here - nothing is
          pre-filled or estimated.
        </p>
      )}
    </Panel>
  );
}
