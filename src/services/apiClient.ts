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
 * Performs a GET and returns the parsed body.
 * Non-2xx responses and `status: false` envelopes are thrown as ApiError.
 */
export async function getJson<T>(path: string, options: { signal?: AbortSignal; timeoutMs?: number } = {}): Promise<T> {
  const { signal, cleanup, timedOut } = combineSignals(options.signal, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const url = `${BASE_URL}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
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
    const serverMessage =
      parsed && typeof parsed === 'object' && 'Message' in parsed && typeof (parsed as ApiEnvelope<unknown>).Message === 'string'
        ? (parsed as ApiEnvelope<unknown>).Message
        : '';
    throw new ApiError(serverMessage || `Request failed (${res.status} ${res.statusText}).`, { httpStatus: res.status });
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

/** Absolute URL for endpoints that return raw bytes (document download). */
export function absoluteUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

export const API_BASE_URL = BASE_URL;
