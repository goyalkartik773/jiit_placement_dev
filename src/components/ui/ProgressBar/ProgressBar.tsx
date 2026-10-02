import './ProgressBar.scss';

interface ProgressBarProps {
  /** Part of the pair — must come from the same feed as `total`. */
  current: number;
  /** Whole of the pair. `<= 0` renders an empty track rather than a guess. */
  total: number;
  /** Additional class on the root (e.g. to colour it from the host's tint). */
  className?: string;
}

/**
 * The ONE progress visual the design system allows: a rounded track, a fill
 * and a cap dot at the fill's end. It is the only markup an "X out of Y"
 * metric may add — a standalone figure gets no visual at all (see
 * `../StatCard/metricKind.ts` for the rule that decides which is which).
 *
 * Decorative by construction: the two numbers it plots are always already
 * printed by the host, so it is `aria-hidden` and never carries meaning on
 * its own.
 *
 * COLOURS: none of its own. Track, fill and cap all read `currentColor`, so
 * the host decides the hue — a `StatCard` passes its `--tile-ink`, a branch
 * row passes its `BRANCH_COLORS` text. The only token read here is
 * `--ui-radius-pill` from `styles/_ui.scss`.
 */
export function ProgressBar({ current, total, className = '' }: ProgressBarProps) {
  const pct = total > 0 ? Math.min(100, Math.max(0, (current / total) * 100)) : 0;
  const classes = ['ui-progress-bar', className].filter(Boolean).join(' ');

  return (
    <span className={classes} aria-hidden="true">
      <span className="ui-progress-bar__track">
        <span className="ui-progress-bar__fill" style={{ width: `${pct}%` }} />
      </span>
      {/* Sibling of the clipped track, so the cap's ring survives at 0% and
          100% instead of being cut in half by `overflow: hidden`. */}
      <span className="ui-progress-bar__cap" style={{ left: `${pct}%` }} />
    </span>
  );
}
