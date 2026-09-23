import { formatINR, formatLpa } from '../../../utils/format';
import { getPackageTier } from '../../../utils/tiers';
import './CtcChip.scss';

interface CtcChipProps {
  /** Annual CTC in INR — exactly the backend's `package` field. */
  package: number | null | undefined;
  /** Fallback text from `packageinfo` when no number exists. */
  packageinfo?: string | null;
  size?: 'sm' | 'md';
  /** Details contexts show the tier word ("High") next to the amount. */
  showTierWord?: boolean;
}

/**
 * The app's canonical money display: a tier-colored pill so users can
 * compare packages across cards at a glance (fixed 5-tier color coding).
 */
export function CtcChip({ package: pkg, packageinfo, size = 'sm', showTierWord = false }: CtcChipProps) {
  const tier = getPackageTier(pkg);
  const lpa = formatLpa(pkg);
  const inr = formatINR(pkg);

  if (tier.key === 'undisclosed') {
    const fallback = (packageinfo ?? '').trim();
    const text = fallback || 'Package not disclosed';
    return (
      <span className={`ctc-chip ctc-chip--undisclosed ctc-chip--${size}`} title={fallback || 'No package information'}>
        {text}
      </span>
    );
  }

  return (
    <span
      className={`ctc-chip ctc-chip--${tier.key} ctc-chip--${size}`}
      title={`${inr} per annum · ${tier.range} (${tier.label} tier)`}
    >
      <span className="ctc-chip__amount">₹{lpa}</span>
      {showTierWord ? <span className="ctc-chip__tier">{tier.label}</span> : null}
    </span>
  );
}
