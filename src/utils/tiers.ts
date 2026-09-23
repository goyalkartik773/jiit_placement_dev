/**
 * ============================================================================
 * Fixed color-coding rules — the single source of truth for the UI's
 * semantic colors. Pure functions, unit-testable, no React.
 *
 * CTC tiers (from the real package distribution: 9/29/19/20/9 jobs):
 *   entry     <  ₹4 LPA      slate   (0.4–4 LPA)
 *   standard  ₹4–8 LPA       blue    (largest bucket)
 *   advanced  ₹8–12 LPA      violet
 *   high      ₹12–20 LPA     gold
 *   premium   ₹20+ LPA       emerald (max = ₹56 LPA)
 *
 * Criteria strictness (real values: CGPA 4.5–8.5, % 50–85, plus one "0"):
 *   relaxed   ≤ 6 CGPA  or ≤ 60 %  (includes "0" = no bar)  → success green
 *   moderate  ≤ 7.5 CGPA or ≤ 75 %                          → warning amber
 *   strict    above                                         → danger red
 * ============================================================================
 */

export type TierKey = 'entry' | 'standard' | 'advanced' | 'high' | 'premium' | 'undisclosed';

export interface PackageTier {
  key: TierKey;
  /** Short word used in legends and stat subtitles. */
  label: string;
  /** Human range for titles/legends: "₹4–8 LPA". */
  range: string;
}

const TIERS: Record<TierKey, PackageTier> = {
  entry: { key: 'entry', label: 'Entry', range: '< ₹4 LPA' },
  standard: { key: 'standard', label: 'Standard', range: '₹4–8 LPA' },
  advanced: { key: 'advanced', label: 'Advanced', range: '₹8–12 LPA' },
  high: { key: 'high', label: 'High', range: '₹12–20 LPA' },
  premium: { key: 'premium', label: 'Premium', range: '₹20+ LPA' },
  undisclosed: { key: 'undisclosed', label: 'Not disclosed', range: '—' },
};

/** Annual CTC in INR → fixed tier. Missing/zero package → "undisclosed". */
export function getPackageTier(packageInr: number | null | undefined): PackageTier {
  if (packageInr === null || packageInr === undefined || !Number.isFinite(packageInr) || packageInr <= 0) {
    return TIERS.undisclosed;
  }
  const lakhs = packageInr / 100_000;
  if (lakhs < 4) return TIERS.entry;
  if (lakhs < 8) return TIERS.standard;
  if (lakhs < 12) return TIERS.advanced;
  if (lakhs < 20) return TIERS.high;
  return TIERS.premium;
}

export type CriteriaTone = 'relaxed' | 'moderate' | 'strict' | 'unknown';

export interface CriteriaAssessment {
  tone: CriteriaTone;
  /** Parsed numeric value; null when the criteria is not numeric. */
  value: number | null;
  /** "6.5 CGPA" / "70 %" display hint; empty for unknown. */
  hint: string;
}

/** Parses a criteria string ("6", "6.5", "70", "0") into a strictness tone. */
export function getCriteriaTone(criteria: string | null | undefined): CriteriaAssessment {
  const raw = (criteria ?? '').trim();
  const value = Number(raw);
  if (raw === '' || !Number.isFinite(value)) {
    return { tone: 'unknown', value: null, hint: '' };
  }
  if (value === 0) {
    // "0" appears once in the data and reads as "no minimum bar".
    return { tone: 'relaxed', value: 0, hint: 'no minimum bar' };
  }
  // Values > 10 are percentages; ≤ 10 are CGPA (real ranges: 4.5–8.5 vs 50–85).
  if (value > 10) {
    const tone: CriteriaTone = value <= 60 ? 'relaxed' : value <= 75 ? 'moderate' : 'strict';
    return { tone, value, hint: `${value} % min.` };
  }
  const tone: CriteriaTone = value <= 6 ? 'relaxed' : value <= 7.5 ? 'moderate' : 'strict';
  return { tone, value, hint: `${value} CGPA min.` };
}

/** Raw level codes → display label ("CLASS_XII" → "Class XII"). */
export function formatLevel(level: string | null | undefined): string {
  const raw = (level ?? '').trim();
  if (!raw) return '—';
  if (raw === 'CLASS_X') return 'Class X';
  if (raw === 'CLASS_XII') return 'Class XII';
  if (raw === 'UG') return 'UG';
  if (raw === 'PG') return 'PG';
  if (raw === 'DUAL') return 'Dual';
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
