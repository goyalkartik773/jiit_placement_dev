import './TierLegend.scss';

/**
 * Compact legend that teaches the fixed color coding to first-time users:
 * CTC tiers (slate → blue → violet → gold → emerald) and criteria
 * strictness (green / amber / red). Rendered above the job grid.
 */
export function TierLegend() {
  return (
    <aside className="tier-legend" aria-label="Color coding legend">
      <span className="tier-legend__group">
        <span className="tier-legend__label">CTC</span>
        <span className="tier-legend__chips">
          <span className="tier-legend__chip tier-legend__chip--entry" title="Entry tier — under ₹4 LPA">
            &lt; ₹4L
          </span>
          <span className="tier-legend__chip tier-legend__chip--standard" title="Standard tier — ₹4 to 8 LPA">
            ₹4–8L
          </span>
          <span className="tier-legend__chip tier-legend__chip--advanced" title="Advanced tier — ₹8 to 12 LPA">
            ₹8–12L
          </span>
          <span className="tier-legend__chip tier-legend__chip--high" title="High tier — ₹12 to 20 LPA">
            ₹12–20L
          </span>
          <span className="tier-legend__chip tier-legend__chip--premium" title="Premium tier — ₹20 LPA and above">
            ₹20L+
          </span>
        </span>
      </span>

      <span className="tier-legend__divider" aria-hidden="true" />

      <span className="tier-legend__group">
        <span className="tier-legend__label">Min. criteria</span>
        <span className="tier-legend__chips">
          <span className="tier-legend__chip tier-legend__chip--relaxed" title="Relaxed — up to 6 CGPA or 60%">
            ≤ 6 CGPA / 60 %
          </span>
          <span className="tier-legend__chip tier-legend__chip--moderate" title="Moderate — up to 7.5 CGPA or 75%">
            ≤ 7.5 / 75 %
          </span>
          <span className="tier-legend__chip tier-legend__chip--strict" title="Strict — above 7.5 CGPA or 75%">
            above
          </span>
        </span>
      </span>
    </aside>
  );
}
