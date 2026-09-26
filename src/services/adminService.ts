import { ApiError, deleteJson, getAuthJson, postJson } from './apiClient';
import type {
  AdminDeleteJobsResponse,
  AdminJobCountResponse,
  AdminLoginResponse,
  AdminLogoutResponse,
  AdminSyncStartResponse,
  AdminSyncStatus,
} from '../types/admin.types';

/**
 * Admin API service — the ONLY place that knows admin endpoint paths.
 *
 * POST   /api/admin/login
 * POST   /api/admin/logout
 * GET    /api/admin/jobs/count
 * POST   /api/admin/jobs/sync
 * GET    /api/admin/jobs/sync/status
 * DELETE /api/admin/jobs
 *
 * The session token lives in sessionStorage (per-tab) and is attached as an
 * `Authorization: Bearer` header. It is never logged or rendered.
 */
const TOKEN_STORAGE_KEY = 'jiit-admin-token';

export function getAdminToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function setAdminToken(token: string): void {
  try {
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    /* storage unavailable (private mode) — session simply won't persist */
  }
}

export function clearAdminToken(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Exchanges credentials for a session token and stores it. Throws ApiError. */
export async function adminLogin(username: string, password: string, signal?: AbortSignal): Promise<string> {
  const response = await postJson<AdminLoginResponse>('/api/admin/login', { username, password }, { signal });

  if (!response.success || !response.token) {
    throw new ApiError(response.message || 'Sign-in failed. Please try again.');
  }

  setAdminToken(response.token);
  return response.token;
}

/** Revokes the session server-side, then clears it locally (best effort). */
export async function adminLogout(signal?: AbortSignal): Promise<void> {
  const token = getAdminToken();
  try {
    if (token) {
      await postJson<AdminLogoutResponse>('/api/admin/logout', undefined, { token, signal });
    }
  } finally {
    clearAdminToken();
  }
}

/** Total jobs currently in the database (DB function, not a client estimate). */
export async function fetchAdminJobCount(signal?: AbortSignal): Promise<number> {
  const response = await getAuthJson<AdminJobCountResponse>('/api/admin/jobs/count', {
    token: getAdminToken(),
    signal,
  });

  if (!response.success || typeof response.totalJobs !== 'number') {
    throw new ApiError(response.message || 'Could not read the job count.');
  }

  return response.totalJobs;
}

/** Starts the single background sync. Throws ApiError(409) if one is running. */
export async function startJobSync(signal?: AbortSignal): Promise<AdminSyncStartResponse> {
  return postJson<AdminSyncStartResponse>('/api/admin/jobs/sync', undefined, {
    token: getAdminToken(),
    signal,
  });
}

/** Live sync snapshot: idle / running / completed / failed. */
export async function fetchSyncStatus(signal?: AbortSignal): Promise<AdminSyncStatus> {
  const response = await getAuthJson<AdminSyncStatus>('/api/admin/jobs/sync/status', {
    token: getAdminToken(),
    signal,
  });

  if (!response || typeof response.status !== 'string') {
    throw new ApiError('The server returned an unexpected sync status.');
  }

  return response;
}

/**
 * Deletes every job record and the documents it owns (records first, then
 * the files). Throws ApiError(409) while a sync (or another deletion) runs.
 */
export async function deleteAllJobs(signal?: AbortSignal): Promise<AdminDeleteJobsResponse> {
  const response = await deleteJson<AdminDeleteJobsResponse>('/api/admin/jobs', {
    token: getAdminToken(),
    signal,
  });

  if (!response.success) {
    throw new ApiError(response.message || 'Deleting the jobs failed.');
  }

  return response;
}
