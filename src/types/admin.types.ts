/**
 * Response shapes of the admin endpoints (see JIITPlacement/README.md).
 * These mirror the backend exactly — counters stay nullable because the
 * server only reports values it actually knows.
 */

/** `idle | running | completed | failed` */
export type AdminSyncState = 'idle' | 'running' | 'completed' | 'failed';

/** POST /api/admin/login */
export interface AdminLoginResponse {
  success: boolean;
  message?: string;
  token?: string;
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

/** POST /api/admin/jobs/sync (202-style start; 409 when one is already running). */
export interface AdminSyncStartResponse {
  success: boolean;
  message?: string;
  syncId?: string;
  status?: string;
}

/** GET /api/admin/jobs/sync/status — every counter is optional/nullable. */
export interface AdminSyncStatus {
  success?: boolean;
  status: AdminSyncState;
  syncId?: string | null;
  message?: string | null;

  totalJobsBeforeSync?: number | null;
  totalJobsAfterSync?: number | null;

  /** Source total — null until the job list has been fetched. */
  jobsTotal?: number | null;
  jobsProcessed?: number | null;
  newJobs?: number | null;
  documentsDownloaded?: number | null;
  documentsFailed?: number | null;
  failedJobs?: number | null;

  /** 0–100 only while the source total is known; otherwise null. */
  progress?: number | null;

  startedAt?: string | null;
  finishedAt?: string | null;
  error?: string | null;
}

/** One measured step of a delete run (real server-side wall clock). */
export interface AdminDeletePhase {
  phase: string;
  durationMs: number;
}

/** POST /api/admin/jobs/sync-offer-students - counters from one real run. */
export interface AdminOfferSyncResponse {
  success: boolean;
  message: string;
  jobsTotal: number;
  jobsMatched: number;
  jobsWithoutPlacements: number;
  studentsConsidered: number;
  studentsMapped: number;
  mappingsInserted: number;
  duplicatesSkipped: number;
  companiesMatched: number;
  companiesSkipped: number;
  totalMappings: number;
  /** ISO timestamp of the run (e.g. "2026-09-27T16:24:12.206128+05:30"). */
  lastRunAt: string;
}

/** DELETE /api/admin/jobs — honest counts of everything that was removed. */
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
