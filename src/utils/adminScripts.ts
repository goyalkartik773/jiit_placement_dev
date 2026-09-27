/**
 * Admin console presentation helpers: script metadata (label/icon/command),
 * run-status labels, duration and counter formatting.
 *
 * Everything displayed with these helpers is derived from API values — the
 * maps below only turn server keys into English labels and icons.
 */
import type { BadgeTone } from '../components/common/Badge/Badge';
import type { IconName } from '../components/common/Icon/Icon';
import type {
  AdminActivityStatus,
  AdminCounters,
  AdminRunStatus,
  AdminScriptAction,
  AdminScriptKey,
  AdminSyncState,
} from '../types/admin.types';

export interface ScriptMeta {
  /** English label used by buttons, history rows and the timeline. */
  label: string;
  icon: IconName;
}

export const SCRIPT_META: Record<AdminScriptKey, ScriptMeta> = {
  login: { label: 'Admin sign in', icon: 'users' },
  logout: { label: 'Admin sign out', icon: 'logout' },
  jobs_sync: { label: 'Superset job sync', icon: 'download' },
  gmail_sync: { label: 'Mailbox sync', icon: 'inbox' },
  offer_sync: { label: 'Job ↔ student sync', icon: 'layers' },
  delete_gmail: { label: 'Delete mailbox', icon: 'trash' },
  delete_mappings: { label: 'Delete mappings', icon: 'trash' },
  delete_jobs: { label: 'Delete all jobs', icon: 'trash' },
};

/** The exact request each console action issues (printed as the `cmd` line). */
export const SCRIPT_COMMANDS: Record<AdminScriptAction, string> = {
  jobs_sync: '$ POST /api/admin/jobs/sync',
  gmail_sync: '$ POST /api/admin/gmail/sync',
  offer_sync: '$ POST /api/admin/jobs/sync-offer-students',
  delete_gmail: '$ DELETE /api/admin/gmail',
  delete_mappings: '$ DELETE /api/admin/jobs/placed-students',
};

/** What each destructive action may touch — shown as tooltip + arm hint. */
export const SCRIPT_SCOPE: Record<AdminScriptAction, string> = {
  jobs_sync: 'Pulls new SuperSet listings into the job table.',
  gmail_sync: 'Fetches new messages from the configured mailbox groups.',
  offer_sync: 'Matches offer students onto existing job listings.',
  delete_gmail: 'Removes the synced mailbox only — parsed e-mails and placement mappings are untouched.',
  delete_mappings: 'Removes only the job ↔ student mapping — rebuild it by re-running the job ↔ student sync.',
};

export function scriptLabel(script: AdminScriptKey | null | undefined): string {
  return script ? (SCRIPT_META[script]?.label ?? script) : 'Unknown script';
}

export function scriptIcon(script: AdminScriptKey | null | undefined): IconName {
  return (script && SCRIPT_META[script]?.icon) || 'terminal';
}

export interface StatusMeta {
  label: string;
  tone: BadgeTone;
}

/**
 * Label for a STORED activity row: a row left `running` means the API
 * restarted mid-run, so it is reported as "interrupted".
 */
export function activityStatusMeta(status: AdminActivityStatus | null | undefined): StatusMeta {
  switch (status) {
    case 'completed':
      return { label: 'Completed', tone: 'success' };
    case 'failed':
      return { label: 'Failed', tone: 'danger' };
    case 'running':
      return { label: 'Interrupted', tone: 'warning' };
    default:
      return { label: 'Unknown', tone: 'neutral' };
  }
}

/** Label for the live status bar (polled script status). */
export function liveStatusMeta(status: AdminSyncState | null | undefined): StatusMeta {
  switch (status) {
    case 'idle':
      return { label: 'Idle', tone: 'neutral' };
    case 'running':
      return { label: 'Running', tone: 'info' };
    case 'completed':
      return { label: 'Completed', tone: 'success' };
    case 'failed':
      return { label: 'Failed', tone: 'danger' };
    default:
      return { label: 'Unknown', tone: 'neutral' };
  }
}

/** "125 ms" / "2.4 s" / "1m 05s" from a server duration; null when unknown. */
export function formatDuration(ms: number | null | undefined): string | null {
  if (typeof ms !== 'number' || !Number.isFinite(ms) || ms < 0) return null;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds - minutes * 60);
  return `${minutes}m ${String(rest).padStart(2, '0')}s`;
}

/** Milliseconds between a run's server start time and now (live elapsed time). */
export function elapsedSince(startedAt: string | null | undefined): string | null {
  if (!startedAt) return null;
  const started = Date.parse(startedAt);
  if (Number.isNaN(started)) return null;
  return formatDuration(Math.max(0, Date.now() - started));
}

/** Server counter keys worth a one-line chip in the run history. */
const HEADLINE_COUNTERS: { key: string; label: string }[] = [
  { key: 'mappingsInserted', label: 'mappings' },
  { key: 'mappingsDeleted', label: 'mappings' },
  { key: 'messagesDeleted', label: 'messages' },
  { key: 'messagesAdded', label: 'new messages' },
  { key: 'jobsDeleted', label: 'jobs' },
  { key: 'newJobs', label: 'new jobs' },
  { key: 'studentsMapped', label: 'students' },
  { key: 'studentsCleared', label: 'students' },
  { key: 'extractionsDeleted', label: 'extractions' },
  { key: 'attachmentsDeleted', label: 'attachments' },
];

function numericValue(source: unknown, key: string): number | null {
  if (!source || typeof source !== 'object') return null;
  const value = (source as Record<string, unknown>)[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** First recognisable counter of a stored run (offer_sync nests them under `stats`). */
export function counterChip(
  counters: Record<string, unknown> | null | undefined,
): { label: string; value: number } | null {
  if (!counters) return null;

  for (const candidate of HEADLINE_COUNTERS) {
    const direct = numericValue(counters, candidate.key);
    if (direct !== null) return { label: candidate.label, value: direct };

    const nested = numericValue(counters.stats, candidate.key);
    if (nested !== null) return { label: candidate.label, value: nested };
  }
  return null;
}

/** English labels for the counter keys the console's "what changed" block prints. */
const COUNTER_LABELS: Record<string, string> = {
  messagesBefore: 'messages before',
  messagesAfter: 'messages after',
  messagesAdded: 'messages added',
  messagesDeleted: 'messages deleted',
  attachmentsBefore: 'attachments before',
  attachmentsAfter: 'attachments after',
  attachmentsAdded: 'attachments added',
  fetched: 'ids fetched',
  newMessages: 'new messages',
  existingMessages: 'already stored',
  processed: 'processed',
  reviewRequired: 'awaiting review',
  failed: 'failed',
  mappingsBefore: 'mappings before',
  mappingsInserted: 'mappings inserted',
  mappingsDeleted: 'mappings deleted',
  studentsBefore: 'students before',
  studentsCleared: 'students cleared',
  studentsMapped: 'students mapped',
  studentsConsidered: 'students considered',
  studentsAdded: 'students added',
  jobsBefore: 'jobs before',
  companiesBefore: 'companies before',
  companiesCleared: 'companies cleared',
  companiesMatched: 'companies matched',
  companiesSkipped: 'companies skipped',
  companiesTouched: 'companies touched',
  extractionsDeleted: 'extractions deleted',
  duplicatesSkipped: 'duplicates skipped',
  jobsTotal: 'jobs listed',
  jobsMatched: 'jobs matched',
  jobsWithoutPlacements: 'jobs without placements',
  totalMappings: 'total mappings',
  newJobs: 'new jobs',
  jobsProcessed: 'jobs processed',
  documentsDownloaded: 'documents downloaded',
  documentsFailed: 'documents failed',
  failedJobs: 'failed jobs',
  jobsDeleted: 'jobs deleted',
  documentRowsDeleted: 'document rows',
  filesDeleted: 'files deleted',
  filesMissing: 'files missing',
  filesFailed: 'files failed',
};

export interface CounterRow {
  label: string;
  value: number;
}

/** Numeric counters with a known label, in a stable order (max `limit` rows). */
export function listCounters(counters: unknown, limit = 12): CounterRow[] {
  return pickCounters(counters, Object.keys(COUNTER_LABELS), limit);
}

/** The same lookup for an explicit key list (order = `keys` order). */
export function pickCounters(counters: unknown, keys: string[], limit = 12): CounterRow[] {
  if (!counters || typeof counters !== 'object') return [];

  const root = counters as Record<string, unknown>;
  // offer_sync nests its numbers under stats/delta/source — search one level
  // deep as well, root values winning when a key exists in both places.
  const sources: Record<string, unknown>[] = [root];
  for (const value of Object.values(root)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      sources.push(value as Record<string, unknown>);
    }
  }

  const rows: CounterRow[] = [];
  for (const key of keys) {
    if (rows.length >= limit) break;
    const label = COUNTER_LABELS[key];
    if (!label) continue;
    for (const source of sources) {
      const value = source[key];
      if (typeof value === 'number' && Number.isFinite(value)) {
        rows.push({ label, value });
        break;
      }
    }
  }
  return rows;
}

/** jobs_sync reports its counters flat on the status payload, not nested. */
const FLAT_STATUS_COUNTERS = [
  'jobsProcessed',
  'newJobs',
  'documentsDownloaded',
  'documentsFailed',
  'failedJobs',
] as const;

/**
 * Counters of a live `GET …/status` answer: the nested `counters` object when
 * the script has one, otherwise the flat jobs_sync fields. Null when the
 * status reported no numeric counters at all.
 */
export function statusCounters(status: AdminRunStatus | null | undefined): AdminCounters | null {
  if (!status) return null;
  if (status.counters && typeof status.counters === 'object') return status.counters as AdminCounters;

  const flat: AdminCounters = {};
  for (const key of FLAT_STATUS_COUNTERS) {
    const value = status[key];
    if (typeof value === 'number' && Number.isFinite(value)) flat[key] = value;
  }
  return Object.keys(flat).length > 0 ? flat : null;
}
