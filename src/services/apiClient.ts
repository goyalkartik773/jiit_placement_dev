import type { ApiEnvelope } from '../types/job.types';

/**
 * Centralized HTTP client.
 * - Base URL comes from .env (VITE_API_BASE_URL) — never hardcoded in components.
 * - Normalizes every failure (network, timeout, HTTP, API-level) into ApiError.
 */
const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5104').replace(/\/+$/, '');

const DEFAULT_TIMEOUT_MS = 20_000;

export class ApiError extends Error {
  readonly httpStatus: number | null;
  readonly isNetworkError: boolean;
  readonly isTimeout: boolean;

  constructor(
    message: string,
    options: { httpStatus?: number | null; isNetworkError?: boolean; isTimeout?: boolean } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.httpStatus = options.httpStatus ?? null;
    this.isNetworkError = options.isNetworkError ?? false;
    this.isTimeout = options.isTimeout ?? false;
  }
}

/** True when the error was caused by the user cancelling (ignore those). */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

function combineSignals(signal: AbortSignal | undefined, timeoutMs: number): { signal: AbortSignal; cleanup: () => void; timedOut: () => boolean } {
  const controller = new AbortController();
  let didTimeout = false;

  const timer = window.setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', onExternalAbort, { once: true });
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timer);
      signal?.removeEventListener('abort', onExternalAbort);
    },
    timedOut: () => didTimeout,
  };
}

/**
 * Options accepted by every request helper.
 * `token` is only sent by the admin endpoints (Authorization: Bearer).
 */
export interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  token?: string | null;
}

/**
 * Server-supplied failure message — the jobs envelope uses `Message`,
 * the admin endpoints use `message`; both are honoured.
 */
function extractServerMessage(parsed: unknown): string {
  if (parsed && typeof parsed === 'object') {
    const candidate = parsed as { Message?: unknown; message?: unknown };
    if (typeof candidate.Message === 'string' && candidate.Message) return candidate.Message;
    if (typeof candidate.message === 'string' && candidate.message) return candidate.message;
  }
  return '';
}

interface RequestDetails extends RequestOptions {
  method: 'GET' | 'POST' | 'DELETE';
  body?: unknown;
}

/** Core request: fetch + timeout/abort handling + uniform ApiError normalization. */
async function requestJson<T>(path: string, details: RequestDetails): Promise<T> {
  const { signal, cleanup, timedOut } = combineSignals(details.signal, details.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const url = `${BASE_URL}${path}`;
  const hasBody = details.body !== undefined && details.body !== null;

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (hasBody) headers['Content-Type'] = 'application/json';
  if (details.token) headers['Authorization'] = `Bearer ${details.token}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: details.method,
      headers,
      body: hasBody ? JSON.stringify(details.body) : undefined,
      signal,
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

  // Read body once; tolerate empty and non-JSON bodies.
  let bodyText = '';
  try {
    bodyText = await res.text();
  } catch {
    /* fall through with empty body */
  }

  let parsed: unknown = null;
  if (bodyText) {
    try {
      parsed = JSON.parse(bodyText);
    } catch {
      parsed = null;
    }
  }

  if (!res.ok) {
    throw new ApiError(extractServerMessage(parsed) || `Request failed (${res.status} ${res.statusText}).`, {
      httpStatus: res.status,
    });
  }

  if (parsed === null) {
    throw new ApiError('The server returned an unexpected (non-JSON) response.', { httpStatus: res.status });
  }

  // API-level failure: { status: false, Message, Data: null }
  if (typeof parsed === 'object' && 'status' in parsed) {
    const envelope = parsed as ApiEnvelope<unknown>;
    if (envelope.status === false) {
      throw new ApiError(envelope.Message || 'The request could not be completed.', { httpStatus: res.status });
    }
  }

  return parsed as T;
}

/**
 * Performs a GET and returns the parsed body.
 * Non-2xx responses and `status: false` envelopes are thrown as ApiError.
 */
export function getJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, { method: 'GET', ...options });
}

/** GET with an `Authorization: Bearer` header (admin endpoints). */
export function getAuthJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, { method: 'GET', ...options });
}

/** POST a JSON body, optionally authenticated (admin endpoints). */
export function postJson<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, { method: 'POST', body, ...options });
}

/** DELETE without a body, optionally authenticated (admin endpoints). */
export function deleteJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, { method: 'DELETE', ...options });
}

/** Absolute URL for endpoints that return raw bytes (document download). */
export function absoluteUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

export const API_BASE_URL = BASE_URL;
