/**
 * WHICH VISUAL A STAT CARD IS ALLOWED TO CARRY.
 *
 * The rule lives here — not in a page — so a card added later cannot quietly
 * grow a decorative chart:
 *
 *   ratio  → the card's own `value` IS "X / Y" and BOTH numbers come from the
 *            SAME feed. Pass `progress={{ current, total }}`; the card renders
 *            the one shared progress bar.
 *
 *   value  → a standalone figure: a ₹ amount, a percentage, or a count whose
 *            feed carries no denominator. Pass NO `progress`; the card shows
 *            number + label + sublabel + icon and nothing else.
 *
 * There is no third case. No rings, dot grids, sliders or sparklines: art
 * that does not plot a real series behind the printed number is decoration
 * pretending to be data. When a genuine trend exists ("average package, last
 * 3 months"), it belongs in a chart component — never in a stat card.
 */
export type MetricKind = 'ratio' | 'value';

/**
 * "X out of Y". Both numbers must be from one feed: mixing a denominator
 * from a second feed produces a figure neither feed ever stated.
 */
export type StatProgress = { current: number; total: number };

/**
 * Derived from the props — never hand-written at the call site — and stamped
 * on the card root as `data-metric-kind`, so a `value` card can be asserted
 * decoration-free in a review or a test.
 */
export function metricKind(progress?: StatProgress): MetricKind {
  return progress ? 'ratio' : 'value';
}
