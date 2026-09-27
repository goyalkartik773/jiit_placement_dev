/**
 * Response shapes of the admin endpoints (see JIITPlacement/README.md).
 * The admin envelope is flat ({ success, message, ... }); the two read
 * endpoints (overview, activity) wrap their payload in `data`. The server
 * omits null values when writing, so every field below is optional and
 * components must tolerate missing data (em dash, never a guess).
 */

/** Live state of a polled script status endpoint. */
export type AdminSyncState = 'idle' | 'running' | 'completed' | 'failed';

/** Stored state of an activity row. A row left `running` by a restart renders as "interrupted". */
export type AdminActivityStatus = 'running' | 'completed' | 'failed';

/** Script keys shared by the activity log and the single server-side run slot. */
export type AdminScriptKey =
  | 'login'
  | 'logout'
  | 'jobs_sync'
  | 'gmail_sync'
  | 'offer_sync'
  | 'delete_gmail'
  | 'delete_mappings'
  | 'delete_jobs';

/** The five console actions: three polled scripts and two synchronous deletes. */
export type AdminScriptAction =
  | 'jobs_sync'
  | 'gmail_sync'
  | 'offer_sync'
  | 'delete_gmail'
  | 'delete_mappings'
  | 'delete_jobs';

/** Tones used by server `output[]` rows; unknown values are mapped to `info`. */
export type AdminOutputTone = 'cmd' | 'info' | 'success' | 'warn' | 'error';

/** One stored console row — rendered verbatim (`time` is "HH:mm:ss"). */
export interface AdminOutputLine {
  time?: string;
  tone?: AdminOutputTone;
  text?: string;
}

/** Arbitrary JSON object stored with an activity row (shape depends on the script). */
export type AdminCounters = Record<string, unknown>;

// ---------------------------------------------------------------- session --

/** POST /api/admin/login */
export interface AdminLoginResponse {
  success: boolean;
  message?: string;
  token?: string;
  username?: string;
  expiresAt?: string;
}

/** POST /api/admin/logout */
export interface AdminLogoutResponse {
  success: boolean;
  message?: string;
}

/** GET /api/admin/jobs/count */
export interface AdminJobCountResponse {
  success: boolean;
  message?: string;
  totalJobs?: number;
}

// ---------------------------------------------------------------- overview --

export interface AdminOverviewCounts {
  jobs?: number | null;
  jobsActive?: number | null;
  notices?: number | null;
  gmailMessages?: number | null;
  gmailAttachments?: number | null;
  emails?: number | null;
  emailsCanonical?: number | null;
  offers?: number | null;
  offerStudents?: number | null;
  mappings?: number | null;
  shortlistEvents?: number | null;
  shortlistStudents?: number | null;
  opportunities?: number | null;
}

/** Mailbox throughput. Rates are 0–100 (1 decimal) and null when the denominator is 0. */
export interface AdminOverviewMailbox {
  total?: number | null;
  processed?: number | null;
  reviewRequired?: number | null;
  irrelevant?: number | null;
  received?: number | null;
  failed?: number | null;
  finishedRate?: number | null;
  reviewRate?: number | null;
}

/** Canonical e-mail classification. `coverage` is 0–100 and may be null. */
export interface AdminOverviewClassification {
  canonical?: number | null;
  classified?: number | null;
  coverage?: number | null;
  shortlistedStudents?: number | null;
}

/** Last job ↔ student matching run. */
export interface AdminOverviewMatching {
  studentsConsidered?: number | null;
  studentsMapped?: number | null;
  jobsMatched?: number | null;
  jobsWithoutPlacements?: number | null;
  companiesMatched?: number | null;
  companiesSkipped?: number | null;
  lastRunAt?: string | null;
}

/** Rows that should not exist — every value must read 0 as "good". */
export interface AdminOverviewIntegrity {
  orphanMappings?: number | null;
  orphanOffers?: number | null;
  duplicateMappings?: number | null;
  blankRolls?: number | null;
}

/** Admin session facts; timestamps may be absent on a fresh database. */
export interface AdminOverviewSession {
  lastLogin?: string | null;
  previousLogin?: string | null;
  lastLogout?: string | null;
  logins?: number | null;
}

/** Newest-first, one entry per script, may be empty. */
export interface AdminOverviewLastRun {
  script?: AdminScriptKey;
  status?: AdminActivityStatus;
  message?: string;
  durationms?: number | null;
  startedat?: string | null;
  finishedat?: string | null;
}

export interface AdminOverview {
  counts?: AdminOverviewCounts;
  mailbox?: AdminOverviewMailbox;
  classification?: AdminOverviewClassification;
  matching?: AdminOverviewMatching;
  integrity?: AdminOverviewIntegrity;
  session?: AdminOverviewSession;
  lastRuns?: AdminOverviewLastRun[];
}

/** GET /api/admin/overview */
export interface AdminOverviewResponse {
  success: boolean;
  message?: string;
  data?: AdminOverview;
}

// ---------------------------------------------------------------- activity --

export interface AdminActivityItem {
  id?: string;
  script?: AdminScriptKey;
  status?: AdminActivityStatus;
  username?: string;
  message?: string;
  counters?: AdminCounters | null;
  output?: AdminOutputLine[] | null;
  error?: string | null;
  durationms?: number | null;
  startedat?: string | null;
  finishedat?: string | null;
}

/** `Items` casing mirrors the server (PagedRows contract). */
export interface AdminActivityPage {
  Items?: AdminActivityItem[];
  TotalCount?: number | null;
  Page?: number | null;
  PageSize?: number | null;
  TotalPages?: number | null;
}

/** GET /api/admin/activity?page&pageSize&script */
export interface AdminActivityResponse {
  success: boolean;
  message?: string;
  data?: AdminActivityPage;
}

export interface AdminActivityQuery {
  /** 1-based; pageSize max 100. */
  page?: number;
  pageSize?: number;
  script?: AdminScriptKey;
}

// --------------------------------------------------------- script commands --

/** POST answers of the three scripts (200 started / 409 conflict). */
export interface AdminScriptStartResponse {
  success: boolean;
  message?: string;
  script?: AdminScriptKey;
  syncId?: string;
  status?: string;
  /** Present on 409: the script that currently holds the shared run slot. */
  busyScript?: AdminScriptKey;
}

/** Every script command answer — deletes reply with their counters inline. */
export interface AdminScriptCommandResponse {
  success?: boolean;
  message?: string;
  script?: AdminScriptKey;
  status?: string;
  syncId?: string;
  busyScript?: AdminScriptKey;
  counters?: AdminCounters | null;
  phases?: AdminDeletePhase[];
  durationMs?: number | null;
  output?: AdminOutputLine[] | null;
  error?: string;
}

/** One measured step of a delete run (real server-side wall clock). */
export interface AdminDeletePhase {
  phase: string;
  durationMs: number;
}

/** DELETE /api/admin/gmail — removes the synced mailbox only.
 *  (type alias on purpose: keeps `Record<string, unknown>` assignability) */
export type AdminDeleteGmailCounters = {
  messagesBefore?: number | null;
  attachmentsBefore?: number | null;
  messagesDeleted?: number | null;
  attachmentsDeleted?: number | null;
  extractionsDeleted?: number | null;
  sqlDurationMs?: number | null;
};

export interface AdminDeleteGmailResponse extends AdminScriptCommandResponse {
  counters?: AdminDeleteGmailCounters | null;
}

/** DELETE /api/admin/jobs/placed-students — mapping rows only, rebuildable.
 *  (type alias on purpose: keeps `Record<string, unknown>` assignability) */
export type AdminDeleteMappingsCounters = {
  mappingsBefore?: number | null;
  studentsBefore?: number | null;
  companiesBefore?: number | null;
  mappingsDeleted?: number | null;
  studentsCleared?: number | null;
  companiesCleared?: number | null;
  sqlDurationMs?: number | null;
};

export interface AdminDeleteMappingsResponse extends AdminScriptCommandResponse {
  counters?: AdminDeleteMappingsCounters | null;
}

/** DELETE /api/admin/jobs — unchanged contract (job rows + documents on disk). */
export interface AdminDeleteJobsResponse {
  success: boolean;
  message?: string;
  jobsDeleted?: number;
  documentRowsDeleted?: number;
  filesDeleted?: number;
  filesMissing?: number;
  filesFailed?: number;
  durationMs?: number;
  phases?: AdminDeletePhase[];
}

// ------------------------------------------------------------ run statuses --

/**
 * GET …/status for any polled script. gmail_sync / offer_sync nest their
 * counters; jobs_sync reports its counters flat on the payload — `counters`
 * stays `unknown` on purpose and is narrowed per script in the UI.
 */
export interface AdminRunStatus {
  success?: boolean;
  script?: AdminScriptKey;
  runId?: string | null;
  syncId?: string | null;
  status: AdminSyncState;
  message?: string | null;
  username?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;
  /** 0–100; only present when the server can compute it. */
  progress?: number | null;
  counters?: unknown;
  output?: AdminOutputLine[] | null;
  error?: string | null;
  /** Measured steps of a synchronous delete run (deletes only). */
  phases?: AdminDeletePhase[] | null;

  /** jobs_sync extras (flat on the payload). */
  totalJobsBeforeSync?: number | null;
  totalJobsAfterSync?: number | null;
  jobsTotal?: number | null;
  jobsProcessed?: number | null;
  newJobs?: number | null;
  documentsDownloaded?: number | null;
  documentsFailed?: number | null;
  failedJobs?: number | null;
}

/** GET /api/admin/jobs/sync/status */
export interface AdminJobsSyncStatus extends AdminRunStatus {
  script?: 'jobs_sync';
}

export interface AdminGmailSyncGroup {
  name?: string;
  email?: string;
  fetched?: number | null;
  newMessages?: number | null;
  existingMessages?: number | null;
  processed?: number | null;
  reviewRequired?: number | null;
  failed?: number | null;
}

export interface AdminGmailSyncCounters {
  messagesBefore?: number | null;
  messagesAfter?: number | null;
  messagesAdded?: number | null;
  attachmentsBefore?: number | null;
  attachmentsAfter?: number | null;
  attachmentsAdded?: number | null;
  fetched?: number | null;
  newMessages?: number | null;
  existingMessages?: number | null;
  processed?: number | null;
  reviewRequired?: number | null;
  failed?: number | null;
  groups?: AdminGmailSyncGroup[] | null;
}

/** GET /api/admin/gmail/sync/status */
export interface AdminGmailSyncStatus extends AdminRunStatus {
  script?: 'gmail_sync';
  counters?: AdminGmailSyncCounters | null;
}

/** Source snapshot — present already while the run is still going. */
export interface AdminOfferSyncSource {
  mappingsBefore?: number | null;
  studentsBefore?: number | null;
  jobsBefore?: number | null;
  jobs?: number | null;
}

export interface AdminOfferSyncStats {
  jobsTotal?: number | null;
  jobsMatched?: number | null;
  jobsWithoutPlacements?: number | null;
  studentsConsidered?: number | null;
  studentsMapped?: number | null;
  mappingsInserted?: number | null;
  duplicatesSkipped?: number | null;
  companiesMatched?: number | null;
  companiesSkipped?: number | null;
  totalMappings?: number | null;
  lastRunAt?: string | null;
}

export interface AdminOfferSyncChange {
  company?: string;
  students?: number | null;
}

/** What THIS run changed — `changes: []` means nothing new (idempotent run). */
export interface AdminOfferSyncDelta {
  mappingsInserted?: number | null;
  studentsAdded?: number | null;
  companiesTouched?: number | null;
  changes?: AdminOfferSyncChange[] | null;
}

export interface AdminOfferSyncIntegrity {
  orphanMappings?: number | null;
  duplicateMappings?: number | null;
  orphanOffers?: number | null;
  blankRolls?: number | null;
  totalMappings?: number | null;
}

export interface AdminOfferSyncCounters {
  mappingsBefore?: number | null;
  studentsBefore?: number | null;
  jobsBefore?: number | null;
  source?: AdminOfferSyncSource | null;
  stats?: AdminOfferSyncStats | null;
  delta?: AdminOfferSyncDelta | null;
  integrity?: AdminOfferSyncIntegrity | null;
}

/** GET /api/admin/jobs/sync-offer-students/status */
export interface AdminOfferSyncStatus extends AdminRunStatus {
  script?: 'offer_sync';
  counters?: AdminOfferSyncCounters | null;
}

/** POST /api/admin/gmail/sync body (all fields optional server-side). */
export interface AdminGmailSyncRequest {
  maxResults?: number;
  query?: string;
  groups?: string[];
}
