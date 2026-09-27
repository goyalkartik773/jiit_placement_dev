import { useCallback, useEffect, useMemo, useState } from 'react';
import { Panel } from '../../common/Panel/Panel';
import { ActionCard, type ActionCardModel, type ActionLive, type ActionPill, type ActionResult, type ActionState } from '../ActionCard/ActionCard';
import { toConsoleLines, type ConsoleLine } from '../ScriptConsole/ScriptConsole';
import {
  SCRIPT_META,
  activityStatusMeta,
  elapsedSince,
  listCounters,
  liveStatusMeta,
  statusCounters,
} from '../../../utils/adminScripts';
import type {
  AdminActivityItem,
  AdminActivityStatus,
  AdminOverviewLastRun,
  AdminRunStatus,
  AdminScriptAction,
  AdminScriptKey,
} from '../../../types/admin.types';
import './ScriptActions.scss';

/** The five console actions, in toolbar order (three syncs, then two deletes). */
const ACTIONS: AdminScriptAction[] = [
  'jobs_sync',
  'gmail_sync',
  'offer_sync',
  'delete_gmail',
  'delete_mappings',
  'delete_jobs',
];

function isAction(script: AdminScriptKey | null | undefined): script is AdminScriptAction {
  return typeof script === 'string' && (ACTIONS as string[]).includes(script);
}

/** A stored row left `running` by a restart reports as interrupted. */
function activityState(status: AdminActivityStatus | undefined): ActionState | null {
  if (status === 'completed' || status === 'failed') return status;
  if (status === 'running') return 'interrupted';
  return null;
}

/** Status pill of a card — labels come from the shared status helpers. */
function pillFor(state: ActionState): ActionPill {
  if (state === 'interrupted') return { ...activityStatusMeta('running'), pulse: false };
  return { ...liveStatusMeta(state), pulse: state === 'running' };
}

/** What changed, from a live `GET …/status` answer. */
interface ResultSource extends ActionResult {
  outputCount: number;
}

function fromStatus(status: AdminRunStatus): ResultSource {
  return {
    rows: listCounters(statusCounters(status), 16),
    phases: status.phases ?? [],
    message: status.message ?? null,
    error: status.error ?? null,
    when: status.finishedAt ?? status.startedAt ?? null,
    durationMs: status.durationMs ?? null,
    outputCount: status.output?.length ?? 0,
  };
}

function fromActivity(item: AdminActivityItem): ResultSource {
  return {
    rows: listCounters(item.counters, 16),
    phases: [],
    message: item.message ?? null,
    error: item.error ?? null,
    when: item.finishedat ?? item.startedat ?? null,
    durationMs: item.durationms ?? null,
    outputCount: item.output?.length ?? 0,
  };
}

/** Nothing was reported → no "what changed" block is rendered at all. */
function hasContent(source: ResultSource): boolean {
  return Boolean(
    source.message || source.error || source.rows.length > 0 || source.phases.length > 0 || source.outputCount > 0,
  );
}

interface ScriptActionsProps {
  /** Script the runner is attached to (drives the live console of one card). */
  action: AdminScriptAction | null;
  /** Live/last status of that script. */
  status: AdminRunStatus | null;
  /** A command is in flight or the tracked script reports `running`. */
  busy: boolean;
  starting: boolean;
  /** The action currently being issued — shows the loader on its button. */
  pendingAction: AdminScriptAction | null;
  /** Server text of the last 409 (another run owns the shared slot). */
  conflict: string | null;
  /** Set when a 409's live log could not be attached. */
  conflictScript: AdminScriptKey | null;
  /** Last command error (failed request, refused command). */
  error: string | null;
  /** Console rows of the attached run: client `cmd` row + server `output[]`. */
  lines: ConsoleLine[];
  /** Archived activity row currently displayed instead of the live console. */
  replay: AdminActivityItem | null;
  /** Newest-first activity rows — the stored run shown by each action card. */
  items: AdminActivityItem[];
  /** `overview.lastRuns` — one authoritative last row per script (any age). */
  lastRuns?: AdminOverviewLastRun[] | null;
  onRun: (action: AdminScriptAction) => void;
  onDismissReplay: () => void;
}

/**
 * "Script actions" section: one ActionCard per API command, each with its
 * own state and its own terminal that only exists once the admin opens it
 * (by running the action, or by asking for its last output).
 *
 * Every value rendered comes from the API — this container only decides
 * which of the already-loaded payloads belongs to which card.
 */
export function ScriptActions({
  action,
  status,
  busy,
  starting,
  pendingAction,
  conflict,
  conflictScript,
  error,
  lines,
  replay,
  items,
  lastRuns,
  onRun,
  onDismissReplay,
}: ScriptActionsProps) {
  // Which cards are expanded — one independent flag per action.
  const [open, setOpen] = useState<Record<string, boolean>>({});
  // The action the last command was issued for (attributes conflict/error).
  const [attempted, setAttempted] = useState<AdminScriptAction | null>(null);
  const [, setTick] = useState(0);

  // The elapsed clock of a running script ticks once a second.
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  // Replaying a stored run opens the card that owns it.
  useEffect(() => {
    if (!isAction(replay?.script)) return;
    const script = replay?.script as AdminScriptAction;
    setOpen((previous) => (previous[script] ? previous : { ...previous, [script]: true }));
  }, [replay]);

  // Newest stored row per script — cards fall back to it after a run.
  const archiveByScript = useMemo(() => {
    const map = new Map<AdminScriptKey, AdminActivityItem>();
    for (const item of items) {
      if (item.script && !map.has(item.script)) map.set(item.script, item);
    }
    return map;
  }, [items]);

  // overview.lastRuns: one authoritative row per script at any age — the
  // status pill stays correct even when that run is no longer on page 1.
  const serverRunByScript = useMemo(() => {
    const map = new Map<AdminScriptKey, AdminOverviewLastRun>();
    for (const run of lastRuns ?? []) {
      if (run.script && !map.has(run.script)) map.set(run.script, run);
    }
    return map;
  }, [lastRuns]);

  const handleRun = useCallback(
    (requested: AdminScriptAction) => {
      setAttempted(requested);
      setOpen((previous) => ({ ...previous, [requested]: true }));
      onRun(requested);
    },
    [onRun],
  );

  const buildModel = useCallback(
    (key: AdminScriptAction): ActionCardModel => {
      const attached = action === key;
      const pending = pendingAction === key;
      const running = pending || (attached && busy);
      const conflictHere = attempted === key ? conflict : null;
      const errorHere = attempted === key ? error : null;
      const replayHere = replay && replay.script === key ? replay : null;
      const archive = archiveByScript.get(key) ?? null;
      const liveStatus = attached ? status : null;

      // ---- console rows of THIS action --------------------------------
      const consoleLines: ConsoleLine[] = replayHere
        ? toConsoleLines(replayHere.output)
        : attached
          ? lines
          : toConsoleLines(archive?.output);

      // ---- state → status pill ----------------------------------------
      const liveState = liveStatus ? liveStatus.status : null;
      // Authoritative last row per script (any age) with the loaded page 1
      // as a fallback — so a card never reports "Idle" for a script that ran.
      const stored =
        activityState(serverRunByScript.get(key)?.status) ?? activityState(archive?.status);
      let state: ActionState;
      if (running) state = 'running';
      else if (liveState && liveState !== 'idle') state = liveState;
      else if (errorHere) state = 'failed';
      else if (stored) state = stored;
      else state = 'idle';

      // ---- live strip (only while this action runs) --------------------
      const live: ActionLive | null = running
        ? {
            message:
              liveStatus?.message ??
              (starting ? 'Command sent — waiting for the server…' : 'Waiting for the first status update…'),
            progress:
              typeof liveStatus?.progress === 'number' && Number.isFinite(liveStatus.progress)
                ? Math.min(100, Math.max(0, Math.round(liveStatus.progress)))
                : null,
            elapsed: elapsedSince(liveStatus?.startedAt),
            rows: listCounters(statusCounters(liveStatus), 8),
          }
        : null;

      // ---- what changed (never shown while the run is still going) -----
      const source: ResultSource | null = replayHere
        ? fromActivity(replayHere)
        : running
          ? null
          : attached && liveStatus && liveStatus.status !== 'idle'
            ? fromStatus(liveStatus)
            : !conflictHere && !errorHere && archive
              ? fromActivity(archive)
              : null;

      return {
        state,
        pill: pillFor(state),
        running,
        pending,
        lines: consoleLines,
        title: replayHere
          ? `replay · ${SCRIPT_META[key].label}`
          : attached
            ? `live · ${SCRIPT_META[key].label}`
            : `archive · ${SCRIPT_META[key].label}`,
        live,
        result: source && hasContent(source) ? source : null,
        replay: replayHere,
        conflict: conflictHere,
        conflictScript: conflictHere ? conflictScript : null,
        error: errorHere,
      };
    },
    [action, archiveByScript, attempted, busy, conflict, conflictScript, error, lines, pendingAction, replay, serverRunByScript, starting, status],
  );

  const meta = busy ? 'run in flight' : undefined;

  return (
    <Panel className="script-actions" icon="terminal" title="Script actions" meta={meta}>
      <div className="script-actions__list">
        {ACTIONS.map((key) => (
          <ActionCard
            key={key}
            action={key}
            model={buildModel(key)}
            open={Boolean(open[key])}
            onOpenChange={(next) => setOpen((previous) => ({ ...previous, [key]: next }))}
            onRun={() => handleRun(key)}
            onDismissReplay={onDismissReplay}
            slotBusy={busy}
          />
        ))}
      </div>
    </Panel>
  );
}
