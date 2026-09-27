import { useEffect, useRef } from 'react';
import type { AdminOutputLine, AdminOutputTone } from '../../../types/admin.types';
import './ScriptConsole.scss';

/** How a line is emphasized — mapped to colors in ScriptConsole.scss. */
export type ConsoleTone = 'cmd' | 'info' | 'success' | 'warn' | 'error' | 'dim';

/** One console row; `time` is the server's "HH:mm:ss" gutter. */
export interface ConsoleLine {
  time?: string;
  tone: ConsoleTone;
  text: string;
}

const KNOWN_TONES: readonly string[] = ['cmd', 'info', 'success', 'warn', 'error', 'dim'];

/** The console keeps the most recent output only. */
const MAX_LINES = 400;

function toConsoleTone(tone: AdminOutputTone | undefined): ConsoleTone {
  return tone && KNOWN_TONES.includes(tone) ? tone : 'info';
}

function hasText(line: AdminOutputLine): line is AdminOutputLine & { text: string } {
  return typeof line.text === 'string';
}

/**
 * Server `output[]` → console rows, rendered verbatim and capped to the
 * visible window. Unknown tones fall back to `info`.
 */
export function toConsoleLines(source: AdminOutputLine[] | null | undefined): ConsoleLine[] {
  if (!Array.isArray(source)) return [];
  const rows = source.filter(hasText);
  const capped = rows.length > MAX_LINES ? rows.slice(rows.length - MAX_LINES) : rows;
  return capped.map((line) => ({ time: line.time, tone: toConsoleTone(line.tone), text: line.text }));
}

interface ScriptConsoleProps {
  lines: ConsoleLine[];
  /** True while an operation runs — shows the blinking block cursor. */
  running?: boolean;
  /** Window title shown in the title bar (the live action name). */
  title?: string;
  /** Terminal status badge: RUNNING… / DONE / FAILED / INTERRUPTED / READY. */
  state?: 'running' | 'done' | 'failed' | 'interrupted' | 'idle';
}

const STATE_LABEL: Record<NonNullable<ScriptConsoleProps['state']>, string> = {
  running: 'RUNNING…',
  done: 'DONE',
  failed: 'FAILED',
  interrupted: 'INTERRUPTED',
  idle: 'READY',
};

/**
 * Terminal-style output surface for the admin scripts. Presentation only:
 * every row comes from the server's stored `output[]` (plus the single `cmd`
 * row a click appends), and the body auto-scrolls like a live console.
 */
export function ScriptConsole({
  lines,
  running = false,
  title = 'admin console',
  state,
}: ScriptConsoleProps) {
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const badge = state ?? (running ? 'running' : 'idle');

  // Keep the newest line on screen whenever output grows or a run starts.
  useEffect(() => {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }, [lines, running]);

  return (
    <section className="script-console" aria-label="Script output">
      <header className="script-console__bar">
        <span className="script-console__dots" aria-hidden="true">
          <span className="script-console__dot script-console__dot--close" />
          <span className="script-console__dot script-console__dot--min" />
          <span className="script-console__dot script-console__dot--max" />
        </span>
        <span className="script-console__title">{title}</span>
        <span className={`script-console__state script-console__state--${badge}`}>
          {STATE_LABEL[badge]}
        </span>
      </header>

      <div className="script-console__body" ref={bodyRef} role="log" aria-live="polite" aria-relevant="additions">
        {lines.length === 0 && !running ? (
          <p className="script-console__line script-console__line--dim">Awaiting command…</p>
        ) : null}

        {lines.map((line, index) => (
          <p key={`${index}-${line.tone}`} className={`script-console__line script-console__line--${line.tone}`}>
            <span className="script-console__time">{line.time ?? ''}</span>
            <span className="script-console__text">{line.text}</span>
          </p>
        ))}

        {running ? (
          <p className="script-console__line script-console__line--dim script-console__line--cursor">
            <span className="script-console__cursor" aria-hidden="true" />
          </p>
        ) : null}
      </div>
    </section>
  );
}
