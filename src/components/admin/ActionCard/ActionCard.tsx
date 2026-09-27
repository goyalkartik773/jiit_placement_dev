import { useEffect, useRef, useState } from 'react';
import { Badge, type BadgeTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { Chip } from '../../common/Chip/Chip';
import { Icon } from '../../common/Icon/Icon';
import { useToast } from '../../common/Toast/Toast';
import { ScriptConsole, type ConsoleLine } from '../ScriptConsole/ScriptConsole';
import {
  ACTION_ACCENT,
  SCRIPT_META,
  SCRIPT_SCOPE,
  actionEndpoint,
  formatDuration,
  scriptLabel,
  type CounterRow,
} from '../../../utils/adminScripts';
import { formatDateTime, formatRelative } from '../../../utils/format';
import type {
  AdminActivityItem,
  AdminDeletePhase,
  AdminScriptAction,
  AdminScriptKey,
} from '../../../types/admin.types';
import './ActionCard.scss';

/** The five console actions — the two deletes are armed before they run. */
const DESTRUCTIVE_ACTIONS: AdminScriptAction[] = ['delete_gmail', 'delete_mappings', 'delete_jobs'];

/** How long a delete button stays armed before it disarms itself. */
const ARM_MS = 4000;

/** Progress is 0–100 — 20 CSS-only segments of 5% each (no inline styles). */
const PROGRESS_SEGMENTS = 20;

/** Current state of one action — drives the status pill and the terminal badge. */
export type ActionState = 'idle' | 'running' | 'completed' | 'failed' | 'interrupted';

/** Status pill (label + tone) resolved from the live status or a stored row. */
export interface ActionPill {
  label: string;
  tone: BadgeTone;
  /** Amber pills pulse while a run is in flight. */
  pulse: boolean;
}

/** Live strip above the terminal: real message, progress and elapsed clock. */
export interface ActionLive {
  message: string;
  progress: number | null;
  elapsed: string | null;
  rows: CounterRow[];
}

/** "What changed" block under the terminal — every value comes from the API. */
export interface ActionResult {
  rows: CounterRow[];
  phases: AdminDeletePhase[];
  message: string | null;
  error: string | null;
  when: string | null;
  durationMs: number | null;
}

/** Everything one action card renders. Built by the container from API data. */
export interface ActionCardModel {
  state: ActionState;
  pill: ActionPill;
  /** This action owns an in-flight run (or its command is still open). */
  running: boolean;
  /** Its POST/DELETE request has not answered yet — shows the button loader. */
  pending: boolean;
  /** Console rows for this action (live log, or stored `output[]`). */
  lines: ConsoleLine[];
  /** Terminal window title — "live · …" / "archive · …" / "replay · …". */
  title: string;
  /** Live strip — only while this action is actually running. */
  live: ActionLive | null;
  /** What changed — only once the run settled (never pre-filled). */
  result: ActionResult | null;
  /** Archived row opened from the run history. */
  replay: AdminActivityItem | null;
  /** Server text of the last 409 that hit this action (shared run slot). */
  conflict: string | null;
  /** Script that owns the slot when its live log could not be attached. */
  conflictScript: AdminScriptKey | null;
  /** Last command error (failed request, refused command). */
  error: string | null;
}

interface ActionCardProps {
  action: AdminScriptAction;
  model: ActionCardModel;
  /** The terminal block is rendered only while the card is expanded. */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Issues the command — the container opens this card and calls the runner. */
  onRun: () => void;
  onDismissReplay: () => void;
  /** Another run owns the shared server-side slot — disables every Run button. */
  slotBusy: boolean;
}

const CONSOLE_STATE: Record<ActionState, 'running' | 'done' | 'failed' | 'interrupted' | 'idle'> = {
  running: 'running',
  completed: 'done',
  failed: 'failed',
  interrupted: 'interrupted',
  idle: 'idle',
};

/**
 * One API action as its own card: a collapsed row (icon badge · name ·
 * endpoint · status pill · Run) that expands into a terminal window the
 * moment the admin runs it — plus the result chips and the copy/download
 * controls of that run. Nothing is rendered before a real call produced it.
 *
 * Presentation only: state, commands and data are passed in.
 */
export function ActionCard({
  action,
  model,
  open,
  onOpenChange,
  onRun,
  onDismissReplay,
  slotBusy,
}: ActionCardProps) {
  const { showToast } = useToast();
  const [armed, setArmed] = useState(false);
  const armTimerRef = useRef<number | null>(null);

  const meta = SCRIPT_META[action];
  const endpoint = actionEndpoint(action);
  const scope = SCRIPT_SCOPE[action];
  const destructive = DESTRUCTIVE_ACTIONS.includes(action);
  const hasOutput = model.lines.length > 0;
  const hasRun = model.state !== 'idle' || hasOutput;

  // Arming a delete auto-disarms after ARM_MS.
  useEffect(() => {
    if (!armed) return;
    armTimerRef.current = window.setTimeout(() => setArmed(false), ARM_MS);
    return () => window.clearTimeout(armTimerRef.current ?? undefined);
  }, [armed]);

  // Escape cancels an armed delete.
  useEffect(() => {
    if (!armed) return;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setArmed(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [armed]);

  useEffect(() => () => window.clearTimeout(armTimerRef.current ?? undefined), []);

  const handleRun = (): void => {
    if (slotBusy) return;
    // Two-step arm: the first click explains the blast radius, the second runs.
    if (destructive && !armed) {
      setArmed(true);
      return;
    }
    window.clearTimeout(armTimerRef.current ?? undefined);
    setArmed(false);
    onRun();
  };

  const asText = (): string =>
    model.lines.map((line) => (line.time ? `${line.time}  ${line.text}` : line.text)).join('\n');

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(asText());
      showToast('Console output copied to the clipboard.', 'success');
    } catch {
      showToast('The browser refused clipboard access.', 'error');
    }
  };

  const handleDownload = (): void => {
    const header = `# ${meta.label} — ${formatDateTime(model.result?.when ?? null)}`;
    const stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 16);
    const slug = meta.label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    const blob = new Blob([`${header}\n${asText()}\n`], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${slug}-${stamp}.log`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const result = model.result;
  const live = model.live;
  const progress = live?.progress ?? null;
  const filledSegments = progress === null ? 0 : Math.round(progress / (100 / PROGRESS_SEGMENTS));

  return (
    <article
      className={`action-card action-card--${ACTION_ACCENT[action]}${open ? ' action-card--open' : ''}`}
      aria-label={meta.label}
    >
      {/* ---------------- Collapsed row ---------------- */}
      <div className="action-card__row">
        <span className="action-card__icon" aria-hidden="true">
          <Icon name={meta.icon} size={18} />
        </span>

        <div className="action-card__id">
          <h3 className="action-card__name">{meta.label}</h3>
          <p className="action-card__desc">
            <code className="action-card__endpoint">{endpoint}</code>
            <span> — {scope}</span>
          </p>
        </div>

        <div className="action-card__controls">
          <Badge tone={model.pill.tone} dot={model.pill.pulse} className="badge--pill action-card__pill">
            {model.pill.label}
          </Badge>

          {hasOutput ? (
            <Button
              variant="ghost"
              size="sm"
              icon={open ? undefined : 'eye'}
              title={open ? 'Collapse this action’s output' : 'Show the stored output of this action'}
              onClick={() => onOpenChange(!open)}
            >
              {open ? 'Hide output' : 'View last output'}
            </Button>
          ) : null}

          <Button
            variant={destructive ? 'danger' : 'primary'}
            size="sm"
            loading={model.pending}
            disabled={slotBusy}
            title={scope}
            className={armed ? 'action-card__run--armed' : undefined}
            onClick={handleRun}
            onBlur={() => setArmed(false)}
          >
            {armed ? 'Confirm' : hasRun ? 'Run again' : 'Run'}
          </Button>
        </div>
      </div>

      {/* ---------------- Two-step arm hint ---------------- */}
      {armed ? (
        <p className="action-card__arm" role="status">
          <Icon name="alert-circle" size={14} />
          <span>
            <strong>{meta.label}</strong> — {scope} Click again within {ARM_MS / 1000} seconds to run, or press Esc
            to cancel.
          </span>
        </p>
      ) : null}

      {/* ---------------- Alerts (shared run slot / failed request) ---------------- */}
      {model.conflict ? (
        <p className="action-card__alert action-card__alert--warn" role="alert">
          <Icon name="alert-circle" size={15} />
          <span>
            {model.conflict}
            {model.conflictScript ? ` Live output from ${scriptLabel(model.conflictScript)} could not be attached.` : ''}
          </span>
        </p>
      ) : null}

      {model.error ? (
        <p className="action-card__alert action-card__alert--error" role="alert">
          <Icon name="alert-circle" size={15} />
          <span>{model.error}</span>
        </p>
      ) : null}

      {/* ---------------- Terminal (only once opened) ---------------- */}
      {open ? (
        <div className="action-card__panel">
          {model.replay ? (
            <p className="action-card__replay" role="status">
              <Icon name="terminal" size={15} />
              <span>
                Showing archived output of <strong>{scriptLabel(model.replay.script)}</strong>
                {model.replay.finishedat ? ` from ${formatDateTime(model.replay.finishedat)}` : ''} — the console is
                not attached to a live run.
              </span>
              <Button variant="ghost" size="sm" onClick={onDismissReplay}>
                Back to live console
              </Button>
            </p>
          ) : null}

          {live ? (
            <div className="action-card__live" role="status" aria-live="polite">
              <span className="action-card__live-msg">{live.message}</span>

              {progress !== null ? (
                <span className="action-card__progress">
                  <span
                    className="action-card__bar"
                    role="progressbar"
                    aria-label="Script progress"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progress}
                  >
                    {Array.from({ length: PROGRESS_SEGMENTS }, (_, index) => (
                      <span
                        key={index}
                        className={`action-card__seg${index < filledSegments ? ' action-card__seg--on' : ''}`}
                        aria-hidden="true"
                      />
                    ))}
                  </span>
                  <span className="action-card__progress-num">{progress}%</span>
                </span>
              ) : null}

              <span className="action-card__elapsed">
                <Icon name="clock" size={12} />
                {live.elapsed ?? '—'}
              </span>

              {live.rows.length > 0 ? (
                <span className="action-card__live-chips">
                  {live.rows.map((row) => (
                    <Chip key={row.label} tone="muted" title={row.label} className="chip--mono">
                      {row.value.toLocaleString()} {row.label}
                    </Chip>
                  ))}
                </span>
              ) : null}
            </div>
          ) : null}

          <ScriptConsole
            lines={model.lines}
            running={model.state === 'running'}
            title={model.title}
            state={CONSOLE_STATE[model.state]}
          />

          {result ? (
            <section className="action-card__result" aria-label="What changed">
              <p className="action-card__result-label">What changed</p>

              {result.rows.length > 0 ? (
                <div className="action-card__chips">
                  {result.rows.map((row) => (
                    <Chip key={row.label} tone="muted" title={row.label} className="chip--mono">
                      {row.value.toLocaleString()} {row.label}
                    </Chip>
                  ))}
                </div>
              ) : null}

              {result.phases.length > 0 ? (
                <ul className="action-card__phases">
                  {result.phases.map((phase) => (
                    <li className="action-card__phase" key={phase.phase}>
                      <span className="action-card__phase-dot" aria-hidden="true" />
                      <span className="action-card__phase-name">{phase.phase}</span>
                      <span className="action-card__phase-time">{formatDuration(phase.durationMs) ?? '—'}</span>
                    </li>
                  ))}
                </ul>
              ) : null}

              {result.message ? <p className="action-card__summary">{result.message}</p> : null}

              {result.error ? (
                <p className="action-card__failure" role="alert">
                  <Icon name="alert-circle" size={14} />
                  <span>{result.error}</span>
                </p>
              ) : null}

              <p className="action-card__meta">
                {result.when ? (
                  <span title={formatDateTime(result.when)}>
                    {formatRelative(result.when) ?? formatDateTime(result.when)}
                  </span>
                ) : null}
                {result.durationMs !== null ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <span>{formatDuration(result.durationMs)}</span>
                  </>
                ) : null}
              </p>

              <div className="action-card__result-actions">
                <Button variant="ghost" size="sm" onClick={() => void handleCopy()} disabled={!hasOutput}>
                  Copy output
                </Button>
                <Button variant="ghost" size="sm" icon="download" onClick={handleDownload} disabled={!hasOutput}>
                  Download
                </Button>
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
