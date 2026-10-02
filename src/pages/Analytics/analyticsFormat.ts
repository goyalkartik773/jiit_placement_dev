/**
 * Display helpers shared by every Analytics tab.
 *
 * `count` and `lpa` deliberately mirror the ones in `BranchStats.tsx` — the two
 * screens read the same endpoint, so the same figure must format the same way
 * on both or a user comparing them will see a discrepancy that isn't there.
 */

/** Count with thousands separators; anything non-finite reads as 0. */
export function count(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '0';
  return value.toLocaleString();
}

/**
 * LPA, up to 2 decimals. `null` is a real "not disclosed" answer and renders an
 * em dash — never a 0, which would claim a ₹0 package was offered.
 */
export function lpa(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

/** Percentage, at most 2 decimals, never a long float. */
export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}%`;
}

/**
 * Leading number of a fine-band label: `'10 - 12 L'` → 10, `'50+ L'` → 50.
 * `'Not disclosed'` has none and returns null, which is exactly how every
 * threshold filter is meant to skip it.
 *
 * Parsed rather than hard-coded by index so a change to `fine_bands` in
 * JIITPlacement/SQL/migration_branch_stats.sql cannot silently shift a
 * threshold onto the wrong bucket.
 */
export function bandFloor(label: string): number | null {
  const match = /^(\d+(?:\.\d+)?)/.exec(label.trim());
  return match ? Number(match[1]) : null;
}

/** `'10 - 12 L'` → `'10-12'`, `'50+ L'` → `'50+'`, `'Not disclosed'` untouched. */
export function shortBand(label: string): string {
  return label.replace(/\s*-\s*/g, '-').replace(/\s*L$/, '').trim();
}

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** `'2026-04'` → `'Apr 26'`; the raw key when it isn't a month. */
export function monthShort(month: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return month;
  const index = Number(match[2]) - 1;
  return index >= 0 && index < 12 ? `${MONTH_SHORT[index]} ${match[1].slice(2)}` : month;
}

/** `'2026-04-15'` → `'15 Apr'`; the raw key when it isn't a date. */
export function dayShort(day: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!match) return day;
  const index = Number(match[2]) - 1;
  return index >= 0 && index < 12 ? `${Number(match[3])} ${MONTH_SHORT[index]}` : day;
}
