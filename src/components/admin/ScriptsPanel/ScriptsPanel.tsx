import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, type BadgeTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Chip } from '../../common/Chip/Chip';
import { Icon } from '../../common/Icon/Icon';
import { Panel } from '../../common/Panel/Panel';
import { useToast } from '../../common/Toast/Toast';
import { ScriptConsole, type ConsoleLine } from '../ScriptConsole/ScriptConsole';
import { formatDateTime, formatRelative } from '../../../utils/format';
import {
  SCRIPT_META,
  SCRIPT_SCOPE,
  activityStatusMeta,
  elapsedSince,
  formatDuration,
  listCounters,
  liveStatusMeta,
  scriptLabel,
  statusCounters,
  type CounterRow,
} from '../../../utils/adminScripts';
import type {
  AdminActivityItem,
  AdminDeletePhase,
  AdminRunStatus,
  AdminScriptAction,
  AdminScriptKey,
} from '../../../types/admin.types';
import './ScriptsPanel.scss';

/** The five console actions, in toolbar order (three syncs, then two deletes). */
const TOOLBAR_ACTIONS: AdminScriptAction[] = ['jobs_sync', 'gmail_sync', 'offer_sync', 'delete_gmail', 'delete_mappings'];

/** Destructive actions explained below the toolbar (their two-step scope). */
const DESTRUCTIVE_ACTIONS: AdminScriptAction[] = ['delete_gmail', 'delete_mappings'];

/** How long a delete button stays armed before it disarms itself. */
const ARM_MS = 4000;

/** Progress is 0–100 — 20 CSS-only segments of 5% each (no inline styles). */
const PROGRESS_SEGMENTS = 20;

/** One uniform "what changed" card, fed by either a live status or an archived row. */
interface ResultView {
  script: AdminScriptKey | null;
  statusLabel: string;
  tone: BadgeTone;
  message: string | null;
  error: string | null;
  rows: CounterRow[];
  phases: AdminDeletePhase[];
  when: string | null;
  durationMs: number | null;
  outputCount: number;
}

function fromStatus(status: AdminRunStatus): ResultView {
  const meta = liveStatusMeta(status.status);
  return {
    script: status.script ?? null,
    statusLabel: meta.label,
    tone: meta.tone,
    message: status.message ?? null,
    error: status.error ?? null,
    rows: listCounters(statusCounters(status), 16),
    phases: status.phases ?? [],
    when: status.finishedAt ?? status.startedAt ?? null,
    durationMs: status.durationMs ?? null,
    outputCount: status.output?.length ?? 0,
  };
}

function fromActivity(item: AdminActivityItem): ResultView {
  const meta = activityStatusMeta(item.status);
  return {
    script: item.script ?? null,
    statusLabel: meta.label,
    tone: meta.tone,
    message: item.message ?? null,
    error: item.error ?? null,
    rows: listCounters(item.counters, 16),
    phases: [],
    when: item.finishedat ?? item.startedat ?? null,
    durationMs: item.durationms ?? null,
    outputCount: item.output?.length ?? 0,
  };
}

interface ScriptsPanelProps {
  /** Script the console is attached to (drives the toolbar spinner). */
  action: AdminScriptAction | null;
  /** Live/last status of that script — the source of the what-changed card. */
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
  /** Console rows: live merged lines, or the archived rows while replaying. */
  lines: ConsoleLine[];
  /** Archived activity row currently displayed instead of the live console. */
  replay: AdminActivityItem | null;
  onRun: (action: AdminScriptAction) => void;
  onDismissReplay: () => void;
}

/**
 * Unified scripts panel: the five console actions (deletes are two-step
 * armed), the live status bar, the "what changed" card of the last run and
 * the terminal window. Every visible value comes from the API — the client
 * only formats it (relative time, percentages, labels).
 */
export function ScriptsPanel({
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
  onRun,
  onDismissReplay,
}: ScriptsPanelProps) {
  const { showToast } = useToast();
  const [armed, setArmed] = useState<AdminScriptAction | null>(null);
  const [, setTick] = useState(0);
  const armTimerRef = useRef<number | null>(null);

  // The elapsed clock of a running script ticks once a second.
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  // Arming a delete auto-disarms after ARM_MS.
  useEffect(() => {
    if (!armed) return;
    armTimerRef.current = window.setTimeout(() => setArmed(null), ARM_MS);
    return () => window.clearTimeout(armTimerRef.current ?? undefined);
  }, [armed]);

  // Escape cancels an armed delete.
  useEffect(() => {
    if (!armed) return;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setArmed(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [armed]);

  useEffect(() => () => window.clearTimeout(armTimerRef.current ?? undefined), []);

  const view = useMemo<ResultView | null>(() => {
    if (replay) return fromActivity(replay);
    if (status && !busy) return fromStatus(status);
    return null;
  }, [replay, status, busy]);

  const hasContent = Boolean(
    view && (view.message || view.error || view.rows.length > 0 || view.phases.length > 0 || view.outputCount > 0),
  );

  const handleAction = (requested: AdminScriptAction): void => {
    if (busy) return;
    const isDelete = DESTRUCTIVE_ACTIONS.includes(requested);

    // Two-step arm: the first click explains the blast radius, the second runs.
    if (isDelete && armed !== requested) {
      setArmed(requested);
      return;
    }

    window.clearTimeout(armTimerRef.current ?? undefined);
    setArmed(null);
    onRun(requested);
  };

  const asText = (): string => lines.map((line) => (line.time ? `${line.time}  ${line.text}` : line.text)).join('\n');

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(asText());
      showToast('Console output copied to the clipboard.', 'success');
    } catch {
      showToast('The browser refused clipboard access.', 'error');
    }
  };

  const handleDownload = (): void => {
    const script = replay?.script ?? status?.script ?? action;
    const header = `# ${scriptLabel(script)} — ${formatDateTime(view?.when ?? null)}`;
    const stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 16);
    const slug = scriptLabel(script).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    const blob = new Blob([`${header}\n${asText()}\n`], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${slug}-${stamp}.log`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const liveMeta = liveStatusMeta(status?.status ?? null);
  const progress =
    typeof status?.progress === 'number' && Number.isFinite(status.progress)
      ? Math.min(100, Math.max(0, Math.round(status.progress)))
      : null;
  const filledSegments = progress === null ? 0 : Math.round(progress / (100 / PROGRESS_SEGMENTS));
  const elapsed = busy ? elapsedSince(status?.startedAt) : null;
  const liveRows = busy ? listCounters(statusCounters(status), 8) : [];
  const consoleTitle = replay
    ? `replay · ${scriptLabel(replay.script)}`
    : action
      ? `live · ${scriptLabel(action)}`
      : 'admin console';

  const meta = busy ? (
    <Badge tone={liveMeta.tone} dot>
      {pendingAction ? `${scriptLabel(pendingAction)} running` : liveMeta.label}
    </Badge>
  ) : view ? (
    <Badge tone={view.tone}>{view.statusLabel}</Badge>
  ) : (
    <Badge tone="neutral">No run yet</Badge>
  );

  return (
    <Panel className="scripts-panel" icon="terminal" title="Script console" meta={meta}>
      <div className="scripts">
        <div className="scripts__main">
          {/* ---------------- Toolbar ---------------- */}
          <div className="scripts__toolbar" role="group" aria-label="Script actions">
            {TOOLBAR_ACTIONS.map((key) => {
              const isArmed = armed === key;
              const isPending = pendingAction === key;
              return (
                <Button
                  key={key}
                  variant={isArmed ? 'danger' : 'soft'}
                  size="sm"
                  icon={SCRIPT_META[key].icon}
                  loading={isPending}
                  disabled={busy}
                  title={SCRIPT_SCOPE[key]}
                  className={isArmed ? 'scripts__action--armed' : undefined}
                  onClick={() => handleAction(key)}
                  onBlur={() => setArmed((current) => (current === key ? null : current))}
                >
                  {isArmed ? 'Confirm' : SCRIPT_META[key].label}
                </Button>
              );
            })}
          </div>

          {armed ? (
            <p className="scripts__arm" role="status">
              <Icon name="alert-circle" size={14} />
              <span>
                <strong>{scriptLabel(armed)}</strong> — {SCRIPT_SCOPE[armed]} Click again within {ARM_MS / 1000}{' '}
                seconds to run, or press Esc to cancel.
              </span>
            </p>
          ) : (
            <ul className="scripts__scope">
              {DESTRUCTIVE_ACTIONS.map((key) => (
                <li className="scripts__scope-item" key={key}>
                  <Icon name="trash" size={13} />
                  <span>
                    <strong>{SCRIPT_META[key].label}:</strong> {SCRIPT_SCOPE[key]}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {/* ---------------- Alerts ---------------- */}
          {conflict ? (
            <p className="scripts__alert scripts__alert--warn" role="alert">
              <Icon name="alert-circle" size={15} />
              <span>
                {conflict}
                {conflictScript ? ` Live output from ${scriptLabel(conflictScript)} could not be attached.` : ''}
              </span>
            </p>
          ) : null}

          {error ? (
            <p className="scripts__alert scripts__alert--error" role="alert">
              <Icon name="alert-circle" size={15} />
              <span>{error}</span>
            </p>
          ) : null}

          {/* ---------------- Live status ---------------- */}
          {busy ? (
            <div className="scripts__status" role="status" aria-live="polite">
              <Badge tone={liveMeta.tone} dot>
                {liveMeta.label}
              </Badge>
              <span className="scripts__status-name">{scriptLabel(pendingAction ?? action)}</span>
              <span className="scripts__status-msg">
                {status?.message ??
                  (starting ? 'Command sent — waiting for the server…' : 'Waiting for the first status update…')}
              </span>

              {progress !== null ? (
                <span className="scripts__progress">
                  <span
                    className="scripts__bar"
                    role="progressbar"
                    aria-label="Script progress"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progress}
                  >
                    {Array.from({ length: PROGRESS_SEGMENTS }, (_, index) => (
                      <span
                        key={index}
                        className={`scripts__seg${index < filledSegments ? ' scripts__seg--on' : ''}`}
                        aria-hidden="true"
                      />
                    ))}
                  </span>
                  <span className="scripts__progress-num">{progress}%</span>
                </span>
              ) : null}

              <span className="scripts__elapsed">
                <Icon name="clock" size={13} />
                {elapsed ?? '—'}
              </span>

              {liveRows.length > 0 ? (
                <span className="scripts__status-chips">
                  {liveRows.map((row) => (
                    <Chip key={row.label} tone="muted" title={row.label}>
                      {row.value.toLocaleString()} {row.label}
                    </Chip>
                  ))}
                </span>
              ) : null}
            </div>
          ) : null}

          {/* ---------------- Replay banner ---------------- */}
          {replay ? (
            <p className="scripts__replay" role="status">
              <Icon name="terminal" size={15} />
              <span>
                Showing archived output of <strong>{scriptLabel(replay.script)}</strong>
                {replay.finishedat ? ` from ${formatDateTime(replay.finishedat)}` : ''} — the console is not attached
                to a live run.
              </span>
              <Button variant="ghost" size="sm" onClick={onDismissReplay}>
                Back to live console
              </Button>
            </p>
          ) : null}

          {/* ---------------- What changed ---------------- */}
          {view && hasContent ? (
            <section className="scripts__result" aria-label="What changed">
              <header className="scripts__result-head">
                <span className="scripts__result-icon" aria-hidden="true">
                  <Icon name="checklist" size={15} />
                </span>
                <h3 className="scripts__result-title">What changed</h3>
                <Badge tone="neutral">{scriptLabel(view.script)}</Badge>
                <Badge tone={view.tone} dot>
                  {view.statusLabel}
                </Badge>
                {view.when ? (
                  <span className="scripts__result-when" title={formatDateTime(view.when)}>
                    {formatRelative(view.when) ?? formatDateTime(view.when)}
                  </span>
                ) : null}
                <span className="scripts__result-spacer" />
                {view.durationMs !== null ? (
                  <span className="scripts__result-dur">{formatDuration(view.durationMs)}</span>
                ) : null}
              </header>

              {view.rows.length > 0 ? (
                <div className="scripts__chips">
                  {view.rows.map((row) => (
                    <Chip key={row.label} tone="muted" title={row.label}>
                      {row.value.toLocaleString()} {row.label}
                    </Chip>
                  ))}
                </div>
              ) : null}

              {view.phases.length > 0 ? (
                <ul className="scripts__phases">
                  {view.phases.map((phase) => (
                    <li className="scripts__phase" key={phase.phase}>
                      <span className="scripts__phase-dot" aria-hidden="true" />
                      <span className="scripts__phase-name">{phase.phase}</span>
                      <span className="scripts__phase-time">{formatDuration(phase.durationMs) ?? '—'}</span>
                    </li>
                  ))}
                </ul>
              ) : null}

              {view.message ? <p className="scripts__message">{view.message}</p> : null}
              {view.error ? (
                <p className="scripts__error" role="alert">
                  <Icon name="alert-circle" size={15} />
                  <span>{view.error}</span>
                </p>
              ) : null}

              <div className="scripts__result-actions">
                <Button variant="ghost" size="sm" onClick={() => void handleCopy()} disabled={lines.length === 0}>
                  Copy output
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  icon="download"
                  onClick={handleDownload}
                  disabled={lines.length === 0}
                >
                  Download
                </Button>
              </div>
            </section>
          ) : (
            !busy && (
              <p className="scripts__hint">
                <Icon name="info" size={15} />
                <span>
                  No run has produced output yet. Execute a script above — its counters, measured phases and full
                  console output appear here. Nothing on this page is pre-filled.
                </span>
              </p>
            )
          )}
        </div>

        {/* ---------------- Console ---------------- */}
        <div className="scripts__console-col">
          <ScriptConsole lines={lines} running={busy && !replay} title={consoleTitle} />
        </div>
      </div>
    </Panel>
  );
}
