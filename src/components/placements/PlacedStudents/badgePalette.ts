import type { PlacedStudent } from '../../../types/dashboard.types';
import { formatINR } from '../../../utils/format';

/**
 * Palette + label helpers shared by the placed-student table and the student
 * detail drawer.
 *
 * Both surfaces must agree on what a branch or role chip looks like, so the
 * colour maps, the lookup and the label shorteners all live here — nothing
 * picks a colour ad-hoc. Both maps are CLOSED sets: any key they do not name
 * falls back to `NEUTRAL_BADGE`, which is how "unknown branch / unknown role"
 * renders.
 */

export interface BadgeColors {
  /** Chip fill. Written inline because the palette is a map, not a class list. */
  bg: string;
  /** Chip text — never the same family as `bg`, so the label stays legible. */
  text: string;
}

/**
 * Neutral chip for everything the palette does not name (Intg. MTech, MTech,
 * JUIT, Other, blank roles, internships...). Reads the app's own tokens where
 * they pass contrast; the text is `$text-soft` (mirrored as a literal here,
 * since this file cannot read SCSS) rather than `--ui-muted`, because
 * `--ui-muted` on `--ui-pill` measures 4.36:1 — just under the 4.5:1 floor
 * these 12px bold labels need.
 */
export const NEUTRAL_BADGE: BadgeColors = { bg: 'var(--ui-pill)', text: '#4a4f59' };

/**
 * Branch palette (from the design mock-up). `student_branch_campus.branch`
 * carries nine values in the live corpus — CSE, ECE, IT and BT are named
 * here; JUIT, Other, MTech, EE-VLSI, EC-ACT and Intg. MTech fall through to
 * `NEUTRAL_BADGE` rather than inventing six more tints.
 */
export const BRANCH_COLORS: Record<string, BadgeColors> = {
  CSE: { bg: '#E6F1FB', text: '#042C53' },
  ECE: { bg: '#EEEDFE', text: '#26215C' },
  IT: { bg: '#E1F5EE', text: '#04342C' },
  BT: { bg: '#EAF3DE', text: '#173404' },
};

/**
 * Role palette.
 *
 * The brief only listed `DSE L1/L2/L3`, but the corpus is the other way
 * round: `Digital Specialist Engineer` ships as ONE untiered role (43 placed
 * Infosys students) while the tiers belong to the Specialist Programmer
 * family (`Specialist Programmer - L1` x41, `- L2` x4). So the map carries
 * the spec's DSE tiers (kept for when they appear), the SP tiers that do
 * appear today, and one untiered key per family — which is what the emails
 * actually produce. Every known Infosys role gets a colour; every other role
 * (GenC, BTSA, internships...) still falls back to neutral.
 *
 * DSE/SP share the ramp's entry tint: they are the base of their families,
 * and no branch colour in `BRANCH_COLORS` is warm, so the Infosys family
 * always reads as a group.
 */
export const ROLE_TIER_COLORS: Record<string, BadgeColors> = {
  'DSE L1': { bg: '#FAECE7', text: '#4A1B0C' },
  'DSE L2': { bg: '#FAEEDA', text: '#412402' },
  'DSE L3': { bg: '#FBEAF0', text: '#4B1528' },
  'SP L1': { bg: '#FAECE7', text: '#4A1B0C' },
  'SP L2': { bg: '#FAEEDA', text: '#412402' },
  'SP L3': { bg: '#FBEAF0', text: '#4B1528' },
  DSE: { bg: '#FAECE7', text: '#4A1B0C' },
  SP: { bg: '#FAECE7', text: '#4A1B0C' },
};

/** The only tags `shortRoleLabel()` is allowed to return as an acronym. */
const KNOWN_ROLE_TAGS = new Set(Object.keys(ROLE_TIER_COLORS));

/** Case-insensitive lookup; unknown keys (and blanks) resolve to neutral. */
export function badgeColors(
  map: Record<string, BadgeColors>,
  value: string | null | undefined,
): BadgeColors {
  const key = (value ?? '').trim().toUpperCase();
  return (key ? map[key] : undefined) ?? NEUTRAL_BADGE;
}

/**
 * The email's own ``Branch`` cell is actual data and wins; the
 * enrollment-range rule (`branchfromroll`) fills the rolls the config cannot
 * resolve — alpha rolls, unconfigured admission years. Null means "neither
 * answered", and callers render a dash rather than the string "null".
 */
export function branchOf(student: PlacedStudent): string | null {
  return (student.branch ?? '').trim() || (student.branchfromroll ?? '').trim() || null;
}

/**
 * Display campus: the roll's `99` prefix, overridden only when the ``University``
 * cell names another institution. Null when neither source answered — in the
 * drawer that row is omitted entirely instead of rendering an empty label.
 */
export function campusOf(student: PlacedStudent): string | null {
  return (student.campus ?? '').trim() || (student.campusfromroll ?? '').trim() || null;
}

/** Raw offer text when the mail carried it, else the annual figure, else a real fallback. */
export function ctcLabel(ctcraw: string | null, ctctotal: number | null): string {
  const raw = (ctcraw ?? '').trim();
  return raw || formatINR(ctctotal) || 'Not disclosed';
}

const TIER_RE = /\bL\s*[-–—]?\s*([123])\b/gi;

/**
 * Short display tag for a role cell — `Specialist Programmer - L1` → `SP L1`,
 * `Digital Specialist Engineer (Trainee)` → `DSE`.
 *
 * `rolelevel` is already canonicalised for GROUPING (`fn_norm_role_v1`
 * rejoins wrapped cells), but a grouping key is not a label: the table has no
 * room for the full sentence. Derived at display time only — never persisted,
 * never sent anywhere.
 *
 * An acronym is only RETURNED when it is a designed, coloured tag (see
 * `ROLE_TIER_COLORS`). Otherwise the role is spelled out in full: inventing
 * initials for arbitrary prose produces things like "NSI" for
 * `Non - SDE Intern` or "ABAASE" for
 * `Associate Business Analyst / Associate Software Engineer`, which are worse
 * than the sentence they replace.
 */
export function shortRoleLabel(student: PlacedStudent): string | null {
  const source = (student.rolelevel ?? '').trim() || (student.role ?? '').trim();
  if (!source) return null;

  // Distinct tiers found anywhere in the cell. More than one (a combined
  // "(L1, L2, L3)" cell) means the student's own tier is unknown, so no tier
  // suffix is appended — an invented tier would be worse than none.
  const tiers = [...new Set(Array.from(source.matchAll(TIER_RE), (m) => `L${m[1]}`))];

  const family = source
    .replace(/\([^)]*\)/g, ' ') // phase markers and tier lists
    .replace(TIER_RE, ' ')
    .replace(/[^A-Za-z0-9]+/g, ' ')
    .trim();

  const words = family.split(/\s+/).filter(Boolean);
  if (words.length === 0) return source;

  const initials = words.length === 1 ? words[0] : words.map((word) => word[0]).join('');
  const tag = (tiers.length === 1 ? `${initials} ${tiers[0]}` : initials).trim();

  return KNOWN_ROLE_TAGS.has(tag.toUpperCase()) ? tag : source.replace(TIER_RE, ' ').replace(/\s+/g, ' ').trim();
}
