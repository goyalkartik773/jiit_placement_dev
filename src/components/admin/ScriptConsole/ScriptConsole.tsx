import { useEffect, useRef } from 'react';
import './ScriptConsole.scss';

/** How a line is emphasized — mapped to colors in ScriptConsole.scss. */
export type ConsoleTone = 'cmd' | 'info' | 'success' | 'warn' | 'error' | 'dim';

/** One output row; the timestamp is captured when the line is produced. */
export interface ConsoleLine {
  id: number;
  time: string;
  tone: ConsoleTone;
  text: string;
}

interface ScriptConsoleProps {
  lines: ConsoleLine[];
  /** True while an operation runs — shows the blinking block cursor. */
  busy?: boolean;
  /** Window title shown in the title bar. */
  title?: string;
}

/**
 * Terminal-style output surface for the admin operations. The component is
 * presentation only: every line is produced by the hook from real server
 * responses, and the body auto-scrolls like a live console.
 */
export function ScriptConsole({ lines, busy = false, title = 'admin console' }: ScriptConsoleProps) {
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // Keep the newest line on screen whenever output grows or a run starts.
  useEffect(() => {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }, [lines, busy]);

  return (
    <section className="script-console" aria-label="Script output">
      <header className="script-console__bar">
        <span className="script-console__dots" aria-hidden="true">
          <span className="script-console__dot script-console__dot--close" />
          <span className="script-console__dot script-console__dot--min" />
          <span className="script-console__dot script-console__dot--max" />
        </span>
        <span className="script-console__title">{title}</span>
        <span className={`script-console__state${busy ? ' script-console__state--busy' : ''}`}>
          {busy ? 'running' : 'ready'}
        </span>
      </header>

      <div className="script-console__body" ref={bodyRef} role="log" aria-live="polite" aria-relevant="additions">
        {lines.length === 0 && !busy ? (
          <p className="script-console__line script-console__line--dim">Awaiting command…</p>
        ) : null}

        {lines.map((line) => (
          <p key={line.id} className={`script-console__line script-console__line--${line.tone}`}>
            <span className="script-console__time">{line.time}</span>
            <span className="script-console__text">{line.text}</span>
          </p>
        ))}

        {busy ? (
          <p className="script-console__line script-console__line--dim script-console__line--cursor">
            <span className="script-console__cursor" aria-hidden="true" />
          </p>
        ) : null}
      </div>
    </section>
  );
}
