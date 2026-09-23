import type { EligibilityMark } from '../../../types/job.types';
import { formatLevel, getCriteriaTone } from '../../../utils/tiers';
import './CriteriaChip.scss';

interface CriteriaChipProps {
  mark: Pick<EligibilityMark, 'level' | 'criteria'>;
  /** Details table shows the level in its own column. */
  hideLevel?: boolean;
}

/**
 * Fixed criteria color coding:
 * green = relaxed (≤6 CGPA / ≤60%), amber = moderate, red = strict.
 * The level name ("UG", "Class XII") stays as text so color is never
 * the only carrier of meaning.
 */
export function CriteriaChip({ mark, hideLevel = false }: CriteriaChipProps) {
  const levelLabel = formatLevel(mark.level);
  const { tone, hint } = getCriteriaTone(mark.criteria);
  const title = `${levelLabel} — ${hint || `criteria ${mark.criteria}`}`;

  return (
    <span className={`criteria-chip criteria-chip--${tone}`} title={title}>
      {!hideLevel ? (
        <>
          <span className="criteria-chip__level">{levelLabel}</span>
          <span className="criteria-chip__sep" aria-hidden="true">
            ·
          </span>
        </>
      ) : null}
      <span className="criteria-chip__value">{mark.criteria}</span>
      {hideLevel && hint ? <span className="criteria-chip__hint">{hint.replace(' min.', '')}</span> : null}
    </span>
  );
}
