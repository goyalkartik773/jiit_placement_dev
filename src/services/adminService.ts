import { API_BASE_URL, ApiError, deleteJson, getAuthJson, isAbortError, postJson } from './apiClient';
import type {
  AdminActivityPage,
  AdminActivityQuery,
  AdminDeleteGmailResponse,
  AdminDeleteJobsResponse,
  AdminDeleteMappingsResponse,
  AdminGmailSyncRequest,
  AdminGmailSyncStatus,
  AdminJobsSyncStatus,
  AdminLoginResponse,
  AdminLogoutResponse,
  AdminJobCountResponse,
  AdminOfferSyncStatus,
  AdminOverview,
  AdminOverviewResponse,
  AdminActivityResponse,
  AdminScriptAction,
  AdminScriptCommandResponse,
  AdminScriptKey,
  AdminScriptStartResponse,
} from '../types/admin.types';

/**
 * Admin API service — the ONLY place that knows admin endpoint paths.
 *
 * POST   /api/admin/login | /api/admin/logout
 * GET    /api/admin/overview | /api/admin/activity
 * GET    /api/admin/jobs/count
 * POST   /api/admin/jobs/sync | /api/admin/gmail/sync | /api/admin/jobs/sync-offer-students
 * GET    …/sync/status of each of the three scripts
 * DELETE /api/admin/gmail | /api/admin/jobs/placed-students | /api/admin/jobs
 *
 * The session token lives in sessionStorage (per-tab) and is attached as an
 * `Authorization: Bearer` header. It is never logged or rendered.
 */
const TOKEN_STORAGE_KEY = 'jiit-admin-token';
const USERNAME_STORAGE_KEY = 'jiit-admin-username';

/** Script commands wait for the server (deletes are synchronous server-side). */
const COMMAND_TIMEOUT_MS = 60_000;

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
    window.sessionStorage.removeItem(USERNAME_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Username reported by the login response (session strip). Never a guess. */
export function getAdminUsername(): string | null {
  try {
    return window.sessionStorage.getItem(USERNAME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function setAdminUsername(username: string | undefined): void {
  try {
    if (username) window.sessionStorage.setItem(USERNAME_STORAGE_KEY, username);
  } catch {
    /* storage unavailable — the strip simply omits the account */
  }
}

/** Exchanges credentials for a session token and stores it. Throws ApiError. */
export async function adminLogin(username: string, password: string, signal?: AbortSignal): Promise<string> {
  const response = await postJson<AdminLoginResponse>('/api/admin/login', { username, password }, { signal });

  if (!response.success || !response.token) {
    throw new ApiError(response.message || 'Sign-in failed. Please try again.');
  }

  setAdminToken(response.token);
  setAdminUsername(response.username);
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

// ------------------------------------------------------------------ reads --

/** Inventory + session facts of the whole console (payload is wrapped in `data`). */
export async function getOverview(signal?: AbortSignal): Promise<AdminOverview> {
  const response = await getAuthJson<AdminOverviewResponse>('/api/admin/overview', {
    token: getAdminToken(),
    signal,
  });

  if (!response.success || !response.data) {
    throw new ApiError(response.message || 'Could not read the console overview.');
  }

  return response.data;
}

/** Paged run history (newest first, pageSize max 100). */
export async function getActivity(query: AdminActivityQuery = {}, signal?: AbortSignal): Promise<AdminActivityPage> {
  const params = new URLSearchParams();
  if (typeof query.page === 'number') params.set('page', String(query.page));
  if (typeof query.pageSize === 'number') params.set('pageSize', String(query.pageSize));
  if (query.script) params.set('script', query.script);
  const search = params.toString();

  const response = await getAuthJson<AdminActivityResponse>(`/api/admin/activity${search ? `?${search}` : ''}`, {
    token: getAdminToken(),
    signal,
  });

  if (!response.success || !response.data) {
    throw new ApiError(response.message || 'Could not read the activity log.');
  }

  return response.data;
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

// -------------------------------------------------------- script commands --

/**
 * A failed/conflicted script command. Extends ApiError (so the usual 401
 * handling keeps working) and carries the two extras a plain ApiError would
 * drop: `busyScript` (409 — who owns the shared run slot) and the server's
 * stored `output[]` (500 — the partial log of the failed run).
 */
export class AdminScriptError extends ApiError {
  readonly busyScript: AdminScriptKey | null;
  readonly output: AdminScriptCommandResponse['output'];

  constructor(
    message: string,
    options: { httpStatus?: number | null; busyScript?: AdminScriptKey | null; output?: AdminScriptCommandResponse['output'] } = {},
  ) {
    super(message, { httpStatus: options.httpStatus ?? null });
    this.name = 'AdminScriptError';
    this.busyScript = options.busyScript ?? null;
    this.output = options.output ?? null;
  }
}

function serverMessage(parsed: unknown): string {
  if (parsed && typeof parsed === 'object') {
    const candidate = parsed as { message?: unknown };
    if (typeof candidate.message === 'string' && candidate.message) return candidate.message;
  }
  return '';
}

/** Caller cancellation + a hard upper bound (mirrors apiClient's combineSignals). */
function commandSignal(
  external: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; cleanup: () => void; timedOut: () => boolean } {
  const controller = new AbortController();
  let didTimeout = false;

  const timer = window.setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);

  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener('abort', onExternalAbort, { once: true });
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timer);
      external?.removeEventListener('abort', onExternalAbort);
    },
    timedOut: () => didTimeout,
  };
}

/**
 * Issues a script command (start or delete) and returns its parsed body.
 *
 * The request goes through fetch directly (same base URL / Bearer pattern as
 * apiClient) because a 409 body carries `busyScript`, which the shared
 * ApiError would discard — the console needs it to attach to the run that
 * already holds the slot. 409 and 500 both throw AdminScriptError.
 */
async function sendScriptCommand(
  method: 'POST' | 'DELETE',
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<AdminScriptCommandResponse> {
  const { signal: requestSignal, cleanup, timedOut } = commandSignal(signal, COMMAND_TIMEOUT_MS);
  const hasBody = body !== undefined && body !== null;
  const token = getAdminToken();

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (hasBody) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: hasBody ? JSON.stringify(body) : undefined,
      signal: requestSignal,
    });
  } catch (error) {
    cleanup();
    if (timedOut()) {
      throw new ApiError('The server took too long to respond. Please try again.', { isTimeout: true });
    }
    if (isAbortError(error)) throw error;
    throw new ApiError('Could not reach the server. Check that the backend is running.', { isNetworkError: true });
  }
  cleanup();

  let bodyText = '';
  try {
    bodyText = await res.text();
  } catch {
    /* fall through with an empty body */
  }

  let parsed: unknown = null;
  if (bodyText) {
    try {
      parsed = JSON.parse(bodyText);
    } catch {
      parsed = null;
    }
  }

  const message = serverMessage(parsed) || `Request failed (${res.status} ${res.statusText}).`;
  const command = (parsed && typeof parsed === 'object' ? parsed : null) as AdminScriptCommandResponse | null;

  if (res.status === 409) {
    throw new AdminScriptError(message || 'Another script is already running.', {
      httpStatus: 409,
      busyScript: command?.busyScript ?? null,
      output: command?.output ?? null,
    });
  }

  if (!res.ok || !command) {
    throw new AdminScriptError(message, { httpStatus: res.status, output: command?.output ?? null });
  }

  if (command.success === false) {
    throw new AdminScriptError(message, { httpStatus: res.status, output: command.output ?? null });
  }

  return command;
}

const COMMAND_FOR: Record<AdminScriptAction, { method: 'POST' | 'DELETE'; path: string }> = {
  jobs_sync: { method: 'POST', path: '/api/admin/jobs/sync' },
  gmail_sync: { method: 'POST', path: '/api/admin/gmail/sync' },
  offer_sync: { method: 'POST', path: '/api/admin/jobs/sync-offer-students' },
  delete_gmail: { method: 'DELETE', path: '/api/admin/gmail' },
  delete_mappings: { method: 'DELETE', path: '/api/admin/jobs/placed-students' },
};

/** Runs any of the five console actions and returns the raw command answer. */
export async function runScript(
  action: AdminScriptAction,
  body?: unknown,
  signal?: AbortSignal,
): Promise<AdminScriptCommandResponse> {
  const command = COMMAND_FOR[action];
  return sendScriptCommand(command.method, command.path, body, signal);
}

/** Starts the Superset job sync (409 → AdminScriptError with `busyScript`). */
export async function startJobSync(signal?: AbortSignal): Promise<AdminScriptStartResponse> {
  return (await runScript('jobs_sync', undefined, signal)) as AdminScriptStartResponse;
}

/** Starts the mailbox sync (optional body: maxResults / query / groups). */
export async function startGmailSync(body?: AdminGmailSyncRequest, signal?: AbortSignal): Promise<AdminScriptStartResponse> {
  return (await runScript('gmail_sync', body, signal)) as AdminScriptStartResponse;
}

/** Starts the job ↔ student sync — stats arrive by polling its status. */
export async function startOfferSync(signal?: AbortSignal): Promise<AdminScriptStartResponse> {
  return (await runScript('offer_sync', undefined, signal)) as AdminScriptStartResponse;
}

/** Deletes the synced mailbox only (synchronous: counters arrive inline). */
export async function deleteGmail(signal?: AbortSignal): Promise<AdminDeleteGmailResponse> {
  return (await runScript('delete_gmail', undefined, signal)) as AdminDeleteGmailResponse;
}

/** Deletes only the job ↔ student mapping rows (rebuildable by re-running the sync). */
export async function deletePlacedStudents(signal?: AbortSignal): Promise<AdminDeleteMappingsResponse> {
  return (await runScript('delete_mappings', undefined, signal)) as AdminDeleteMappingsResponse;
}

// ------------------------------------------------------------ run statuses --

function requireStatus<T>(response: T, what: string): T {
  const status = (response as { status?: unknown } | null)?.status;
  if (typeof status !== 'string') {
    throw new ApiError(`The server returned an unexpected ${what} status.`);
  }
  return response;
}

/** Live snapshot of the Superset job sync: idle / running / completed / failed. */
export async function fetchSyncStatus(signal?: AbortSignal): Promise<AdminJobsSyncStatus> {
  const response = await getAuthJson<AdminJobsSyncStatus>('/api/admin/jobs/sync/status', {
    token: getAdminToken(),
    signal,
  });
  return requireStatus(response, 'sync');
}

/** Live snapshot of the mailbox sync (counters are nested under `counters`). */
export async function getGmailSyncStatus(signal?: AbortSignal): Promise<AdminGmailSyncStatus> {
  const response = await getAuthJson<AdminGmailSyncStatus>('/api/admin/gmail/sync/status', {
    token: getAdminToken(),
    signal,
  });
  return requireStatus(response, 'mailbox sync');
}

/** Live snapshot of the job ↔ student sync (stats / delta / integrity). */
export async function getOfferSyncStatus(signal?: AbortSignal): Promise<AdminOfferSyncStatus> {
  const response = await getAuthJson<AdminOfferSyncStatus>('/api/admin/jobs/sync-offer-students/status', {
    token: getAdminToken(),
    signal,
  });
  return requireStatus(response, 'job ↔ student sync');
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
