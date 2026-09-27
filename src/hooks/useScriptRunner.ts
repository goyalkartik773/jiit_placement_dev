import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useToast } from '../components/common/Toast/Toast';
import { toConsoleLines, type ConsoleLine } from '../components/admin/ScriptConsole/ScriptConsole';
import { ApiError, isAbortError } from '../services/apiClient';
import {
  AdminScriptError,
  fetchSyncStatus,
  getGmailSyncStatus,
  getOfferSyncStatus,
  runScript,
} from '../services/adminService';
import { SCRIPT_COMMANDS } from '../utils/adminScripts';
import type {
  AdminOutputLine,
  AdminRunStatus,
  AdminScriptAction,
  AdminScriptKey,
} from '../types/admin.types';

/** Server-side scripts take seconds to minutes; 1.5s keeps the log honest. */
const STATUS_POLL_MS = 1500;

/**
 * Polls that may still be looking at the pre-run snapshot (status not flipped
 * yet / transient failure) before the console stops waiting for the run.
 */
const MAX_SETTLE_POLLS = 8;

/** The console keeps the most recent output only. */
const MAX_LOG_LINES = 400;

type StatusFetcher = (signal?: AbortSignal) => Promise<AdminRunStatus>;

/** Status endpoint of each polled script; the deletes answer synchronously. */
const STATUS_FETCHER: Record<AdminScriptAction, StatusFetcher | null> = {
  jobs_sync: fetchSyncStatus,
  gmail_sync: getGmailSyncStatus,
  offer_sync: getOfferSyncStatus,
  delete_gmail: null,
  delete_mappings: null,
};

/** Identity of one run: a new run always has a new id. */
function runKey(status: AdminRunStatus): string | null {
  return status.runId ?? status.syncId ?? null;
}

function nowTime(): string {
  return new Date().toLocaleTimeString('en-GB', { hour12: false });
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.httpStatus === 401;
}

export interface ScriptRunnerController {
  /** Script whose status the console is attached to (running or last run). */
  action: AdminScriptAction | null;
  status: AdminRunStatus | null;
  /** True while a command is in flight or the tracked script reports `running`. */
  busy: boolean;
  starting: boolean;
  /** The action currently being issued — drives `aria-busy` on its button. */
  pendingAction: AdminScriptAction | null;
  error: string | null;
  /** Server text of the last 409 (the script that owns the shared run slot). */
  conflict: string | null;
  /** Script reported by a 409 when its status could not be attached. */
  conflictScript: AdminScriptKey | null;
  /** Live console lines: one client `cmd` row per click + the server's `output[]`. */
  lines: ConsoleLine[];
  start: (action: AdminScriptAction) => void;
}

/**
 * Drives the console: issues one of the five script commands, polls THAT
 * script's status endpoint while it runs and renders the server's stored
 * `output[]` — no line is ever synthesised beyond the single `cmd` row a
 * click appends (the server echoes it as the first row of its own log).
 *
 * A 409 adopts the returned `busyScript` and attaches to its live run, so
 * two tabs (or a double click) still show the real log. `onSettled` fires
 * whenever a run finishes so the caller can refresh overview + history.
 */
export function useScriptRunner(
  token: string | null,
  onUnauthorized: () => void,
  onSettled: () => void,
): ScriptRunnerController {
  const { showToast } = useToast();

  const [action, setAction] = useState<AdminScriptAction | null>(null);
  const [status, setStatus] = useState<AdminRunStatus | null>(null);
  const [active, setActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [pendingAction, setPendingAction] = useState<AdminScriptAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [conflictScript, setConflictScript] = useState<AdminScriptKey | null>(null);
  const [clientLines, setClientLines] = useState<ConsoleLine[]>([]);
  const [serverLines, setServerLines] = useState<ConsoleLine[]>([]);
  const [pollTick, setPollTick] = useState(0);

  // Run bookkeeping for the tracked run.
  const baselineRef = useRef<string | null | undefined>(undefined);
  const sawRunningRef = useRef(false);
  const settleRef = useRef(0);
  const startingRef = useRef(false);
  const startedRef = useRef(false);

  const onUnauthorizedRef = useRef(onUnauthorized);
  const onSettledRef = useRef(onSettled);
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
    onSettledRef.current = onSettled;
  }, [onUnauthorized, onSettled]);

  const applyOutput = useCallback((output: AdminOutputLine[] | null | undefined): void => {
    setServerLines(toConsoleLines(output));
  }, []);

  /** A run reached its terminal state: stop polling, announce it once. */
  const finishRun = useCallback(
    (next: AdminRunStatus): void => {
      setActive(false);
      if (next.message) {
        showToast(next.message, next.status === 'completed' ? 'success' : 'error');
      }
      onSettledRef.current();
    },
    [showToast],
  );

  const attachRun = useCallback(
    (nextAction: AdminScriptAction, next: AdminRunStatus): void => {
      setAction(nextAction);
      setStatus(next);
      applyOutput(next.output);
    },
    [applyOutput],
  );

  /**
   * Attach to a run and keep polling until it settles. `baseline` is the run
   * id observed BEFORE the command was issued (`null` = none yet, `undefined`
   * = unknown), which is what tells a fast run apart from the previous one.
   */
  const adoptRun = useCallback(
    (nextAction: AdminScriptAction, next: AdminRunStatus, baseline: string | null | undefined): void => {
      attachRun(nextAction, next);

      baselineRef.current = baseline;
      sawRunningRef.current = next.status === 'running';
      settleRef.current = 0;

      if (next.status === 'running' || next.status === 'idle') {
        setActive(true);
        return;
      }

      const key = runKey(next);
      const finishedNewRun = baseline !== undefined && key !== null && key !== baseline;
      if (finishedNewRun) {
        finishRun(next);
        return;
      }
      // Possibly still the pre-run snapshot — bounded polling decides.
      setActive(true);
    },
    [attachRun, finishRun],
  );

  // ---- Console row bookkeeping -------------------------------------------
  // The server echoes the command as the first row of its own log; when it
  // does, our copy is dropped so lines are never duplicated.
  const lines = useMemo(() => {
    if (serverLines.length === 0) return clientLines;
    const merged = [...clientLines, ...serverLines];
    const lastClient = clientLines[clientLines.length - 1];
    const firstServer = serverLines[0];
    if (lastClient && firstServer && lastClient.text === firstServer.text && lastClient.tone === firstServer.tone) {
      merged.shift();
    }
    return merged.length > MAX_LOG_LINES ? merged.slice(merged.length - MAX_LOG_LINES) : merged;
  }, [clientLines, serverLines]);

  // ---- Session reset (sign-out) ------------------------------------------
  useEffect(() => {
    if (token) return;
    setAction(null);
    setStatus(null);
    setActive(false);
    setStarting(false);
    setPendingAction(null);
    setError(null);
    setConflict(null);
    setConflictScript(null);
    setClientLines([]);
    setServerLines([]);
    baselineRef.current = undefined;
    sawRunningRef.current = false;
    settleRef.current = 0;
    startingRef.current = false;
    startedRef.current = false;
  }, [token]);

  // ---- Boot: adopt a run that is already in progress (another tab) -------
  useEffect(() => {
    if (!token) return;

    const controller = new AbortController();
    let cancelled = false;
    const probe = (fetcher: StatusFetcher) => fetcher(controller.signal).catch(() => null);

    Promise.all([probe(fetchSyncStatus), probe(getGmailSyncStatus), probe(getOfferSyncStatus)]).then((results) => {
      if (cancelled || controller.signal.aborted) return;
      if (startedRef.current) return; // a command was issued first — it owns the console

      const found = results.filter((value): value is AdminRunStatus => value !== null);
      const running = found.find((value) => value.status === 'running');
      const startedAtOf = (value: AdminRunStatus): number => {
        const parsed = Date.parse(value.startedAt ?? '');
        return Number.isNaN(parsed) ? 0 : parsed;
      };
      const previous = found
        .filter((value) => value.status !== 'idle')
        .sort((a, b) => startedAtOf(b) - startedAtOf(a))[0];
      const pick = running ?? previous;
      if (!pick) return;

      const pickedAction =
        pick.script === 'jobs_sync' || pick.script === 'gmail_sync' || pick.script === 'offer_sync'
          ? pick.script
          : null;
      if (!pickedAction) return;

      attachRun(pickedAction, pick);
      if (pick.status === 'running') {
        baselineRef.current = runKey(pick);
        sawRunningRef.current = true;
        settleRef.current = 0;
        setActive(true);
      }
    });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [token, attachRun]);

  // ---- Poll while the tracked script runs --------------------------------
  useEffect(() => {
    if (!token || !active || !action) return;
    const fetcher = STATUS_FETCHER[action];
    if (!fetcher) {
      setActive(false); // synchronous commands have no status endpoint
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetcher(controller.signal)
        .then((next) => {
          if (controller.signal.aborted) return;
          setStatus(next);
          applyOutput(next.output);

          if (next.status === 'running') {
            sawRunningRef.current = true;
            settleRef.current = 0;
            setPollTick((value) => value + 1);
            return;
          }

          if (next.status === 'idle') {
            settleRef.current += 1;
            if (settleRef.current < MAX_SETTLE_POLLS) setPollTick((value) => value + 1);
            else setActive(false); // the command never produced a run
            return;
          }

          const key = runKey(next);
          const isNewRun = baselineRef.current !== undefined && key !== null && key !== baselineRef.current;
          if (sawRunningRef.current || isNewRun) {
            finishRun(next);
            return;
          }

          settleRef.current += 1;
          if (settleRef.current < MAX_SETTLE_POLLS) setPollTick((value) => value + 1);
          else setActive(false);
        })
        .catch((caught: unknown) => {
          if (controller.signal.aborted || isAbortError(caught)) return;
          if (isUnauthorized(caught)) {
            onUnauthorizedRef.current();
            setActive(false);
            return;
          }
          // Transient polling failure: keep the last state, retry a few times.
          settleRef.current += 1;
          if (settleRef.current < MAX_SETTLE_POLLS) setPollTick((value) => value + 1);
          else setActive(false);
        });
    }, STATUS_POLL_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [token, active, action, pollTick, applyOutput, finishRun]);

  // ---- Run a command -----------------------------------------------------
  const start = useCallback(
    async (requested: AdminScriptAction): Promise<void> => {
      if (!token || startingRef.current) return;

      startingRef.current = true;
      startedRef.current = true;
      setStarting(true);
      setPendingAction(requested);
      setError(null);
      setConflict(null);
      setConflictScript(null);

      // Fresh view: one client-side `cmd` row until the server's log arrives.
      setAction(requested);
      setStatus(null);
      setActive(false);
      setServerLines([]);
      setClientLines([{ time: nowTime(), tone: 'cmd', text: SCRIPT_COMMANDS[requested] }]);

      const fetcher = STATUS_FETCHER[requested];

      try {
        // Baseline first: what the status says BEFORE this command, so a run
        // that finishes quickly is not mistaken for the previous one.
        let baseline: string | null | undefined = null;
        if (fetcher) {
          try {
            baseline = runKey(await fetcher());
          } catch (caught: unknown) {
            if (isUnauthorized(caught)) {
              onUnauthorizedRef.current();
              return;
            }
            baseline = undefined; // unknown — fall back to bounded settling
          }
        }

        const answer = await runScript(requested);

        if (!fetcher) {
          // Deletes answer synchronously with their counters and log.
          setAction(requested);
          setStatus({
            script: requested,
            status: 'completed',
            message: answer.message ?? null,
            counters: answer.counters ?? null,
            output: answer.output ?? null,
            durationMs: answer.durationMs ?? null,
            phases: answer.phases ?? null,
          });
          applyOutput(answer.output);
          if (answer.message) showToast(answer.message, 'success');
          onSettledRef.current();
          return;
        }

        adoptRun(requested, await fetcher(), baseline);
      } catch (caught: unknown) {
        if (isAbortError(caught)) return;
        if (isUnauthorized(caught)) {
          onUnauthorizedRef.current();
          return;
        }

        if (caught instanceof AdminScriptError && caught.httpStatus === 409 && caught.busyScript) {
          // Another run owns the slot — adopt it and show its live log.
          const busyScript = caught.busyScript;
          setConflict(caught.message);
          setClientLines((prev) => [...prev, { time: nowTime(), tone: 'warn', text: `! ${caught.message}` }]);

          const busyAction =
            busyScript === 'jobs_sync' || busyScript === 'gmail_sync' || busyScript === 'offer_sync'
              ? busyScript
              : null;

          if (busyAction) {
            try {
              const live = await STATUS_FETCHER[busyAction]?.();
              if (!live) {
                setConflictScript(busyScript);
              } else if (live.status === 'running' || live.status === 'idle') {
                adoptRun(busyAction, live, runKey(live));
              } else {
                attachRun(busyAction, live);
              }
            } catch (statusError: unknown) {
              setConflictScript(busyScript);
              if (!isAbortError(statusError) && !isUnauthorized(statusError)) {
                setError(statusError instanceof Error ? statusError.message : 'Could not read the running script.');
              }
            }
          } else {
            // A synchronous delete holds the slot — there is no status to attach.
            setConflictScript(busyScript);
          }
          return;
        }

        const message = caught instanceof Error ? caught.message : 'The command could not be completed.';
        setError(message);
        setClientLines((prev) => [...prev, { time: nowTime(), tone: 'error', text: `✗ ${message}` }]);
        // A failed delete still returns the partial log it produced.
        if (caught instanceof AdminScriptError && caught.output?.length) {
          setServerLines(toConsoleLines(caught.output));
        }
      } finally {
        startingRef.current = false;
        setStarting(false);
        setPendingAction(null);
      }
    },
    [token, adoptRun, applyOutput, attachRun, showToast],
  );

  return {
    action,
    status,
    busy: starting || active || status?.status === 'running',
    starting,
    pendingAction,
    error,
    conflict,
    conflictScript,
    lines,
    start,
  };
}
