import { BRANCH_COLORS, ROLE_TIER_COLORS, badgeColors, type BadgeColors } from './badgePalette';

/**
 * Colour-coded chips for the placed-student table and the detail drawer.
 *
 * Colour is decoration only: every chip carries a real text label, so the cell
 * still reads for anyone who cannot separate the tints, and a value the
 * palette does not name never renders as an empty or "undefined" chip — the
 * caller gets `null` back and shows a dash instead.
 */

function FillBadge({ label, colors, wrap }: { label: string; colors: BadgeColors; wrap?: boolean }) {
  return (
    <span
      className={['placed-students__badge', wrap ? 'placed-students__badge--wrap' : null]
        .filter(Boolean)
        .join(' ')}
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {label}
    </span>
  );
}

/**
 * Campus has no palette in the brief, and its value set overlaps the branch
 * one — `JUIT` is BOTH a branch and a campus in the live corpus — so a second
 * neutral fill would put two identical gray chips side by side. An outlined
 * chip keeps the two columns tellable apart without inventing colours.
 */
function OutlineBadge({ label }: { label: string }) {
  return <span className="placed-students__badge placed-students__badge--outline">{label}</span>;
}

/** Branch chip; `null` (rendered as a dash by the caller) when neither source answered. */
export function BranchBadge({ branch }: { branch: string | null }) {
  if (!branch) return null;
  return <FillBadge label={branch} colors={badgeColors(BRANCH_COLORS, branch)} />;
}

/** Campus chip; `null` when neither the ``University`` cell nor the roll rule answered. */
export function CampusBadge({ campus }: { campus: string | null }) {
  if (!campus) return null;
  return <OutlineBadge label={campus} />;
}

/**
 * Role chip. `role` must already be the SHORT label from `shortRoleLabel()`
 * (e.g. `SP L1`), because that is exactly the key the palette is filed under.
 */
export function RoleBadge({ role }: { role: string | null }) {
  if (!role) return null;
  // Designed tags (DSE, SP L1) stay on one line; a spelled-out role wraps
  // instead of forcing the column to grow to its full length.
  return <FillBadge label={role} colors={badgeColors(ROLE_TIER_COLORS, role)} wrap={role.length > 18} />;
}
