import type { JobDetail } from '../../../types/job.types';
import { formatDate, formatINR, formatLpa, formatRelative, isPast } from '../../../utils/format';
import { getCriteriaTone, getPackageTier, type CriteriaTone } from '../../../utils/tiers';
import './JobMetrics.scss';

interface JobMetricsProps {
  job: JobDetail;
}

/** Strictness ladder for picking the strictest criterion on the job. */
const TONE_RANK: Record<CriteriaTone, number> = { unknown: 0, relaxed: 1, moderate: 2, strict: 3 };

/**
 * Editorial metrics strip (spec): four figures on ONE surface — uppercase
 * label, headline figure, quiet qualifier — divided by hairlines instead of
 * four boxed tiles.
 *
 * The tiles it replaces were 169px of card chrome (border, shadow, icon badge,
 * status pill, dashed footer row) wrapped around a single number each: at
 * 1133px wide the bento row stood taller than the toolbar on the list page.
 * All four subjects survive, at roughly half the height, with the state words
 * (CLOSED/OPEN, tier, strictness) folded into the qualifier line instead of
 * riding in a separate pill.
 *
 * Pure API data from GET /api/jobs/{id}. 0/null falls back to "Not disclosed";
 * tier and strictness keep the fixed colour coding in utils/tiers.ts, and no
 * state is signalled by colour alone — the word is always on the line too.
 */
export function JobMetrics({ job }: JobMetricsProps) {
  const tier = getPackageTier(job.package);
  const lpa = formatLpa(job.package);
  const deadlinePassed = job.deadline ? isPast(job.deadline) : false;
  const deadlineRel = job.deadline ? formatRelative(job.deadline) : null;
  const postedAt = job.posteddatetime ?? job.createdat;

  const marks = Array.isArray(job.eligiblitymarks) ? job.eligiblitymarks.filter(Boolean) : [];
  const criteriaText = marks.map((mark) => mark.criteria).join(' · ');
  const criteriaHints = marks
    .map((mark) => getCriteriaTone(mark.criteria).hint)
    .filter(Boolean)
    .join(' · ');

  let strictest: CriteriaTone | null = null;
  for (const mark of marks) {
    const tone = getCriteriaTone(mark.criteria).tone;
    if (strictest === null || TONE_RANK[tone] > TONE_RANK[strictest]) strictest = tone;
  }
  // "unknown" is a non-numeric criterion — there is no strictness word for it,
  // so the figure stays blank and the raw criteria carry the sub line.
  const strictWord = strictest && strictest !== 'unknown' ? strictest.toUpperCase() : null;

  return (
    <div className="metrics" aria-label="Key job metrics">
      {/* Registration closes */}
      <div className="metrics__cell">
        <span className="metrics__label">Registration closes</span>
        <span
          className={[
            'metrics__value',
            job.deadline ? (deadlinePassed ? 'metrics__value--rose' : null) : 'metrics__value--empty',
          ]
            .filter(Boolean)
            .join(' ')}
          title={job.deadline ? formatDate(job.deadline) : undefined}
        >
          {job.deadline ? formatDate(job.deadline) : 'Not disclosed'}
        </span>
        <span className="metrics__sub">
          {job.deadline
            ? `${deadlinePassed ? 'CLOSED' : 'OPEN'}${deadlineRel ? ` · ${deadlineRel}` : ''}`
            : `Posted ${postedAt ? formatDate(postedAt) : '—'}`}
        </span>
      </div>

      {/* Package pool */}
      <div className="metrics__cell">
        <span className="metrics__label">Package pool</span>
        <span
          className={['metrics__value', lpa ? `metrics__value--${tier.key}` : 'metrics__value--empty']
            .filter(Boolean)
            .join(' ')}
          title={lpa ? `₹${lpa} per annum · ${tier.range}` : undefined}
        >
          {lpa ? `₹${lpa}` : 'Not disclosed'}
        </span>
        <span className="metrics__sub">{lpa ? `${formatINR(job.package)} · ${tier.label}` : '—'}</span>
      </div>

      {/* Hiring category */}
      <div className="metrics__cell">
        <span className="metrics__label">Hiring category</span>
        <span className="metrics__value metrics__value--sm" title={job.placementcategory || undefined}>
          {job.placementcategory || 'Not disclosed'}
        </span>
        <span className="metrics__sub">
          {[job.placementcategorycode ? `Code ${job.placementcategorycode}` : '—', job.placementtype || '—'].join(
            ' · ',
          )}
        </span>
      </div>

      {/* Selection rules */}
      <div className="metrics__cell">
        <span className="metrics__label">Selection rules</span>
        <span
          className={[
            'metrics__value',
            strictWord ? `metrics__value--${strictest}` : 'metrics__value--empty',
          ]
            .filter(Boolean)
            .join(' ')}
          title={criteriaText || undefined}
        >
          {strictWord ?? '—'}
        </span>
        <span className="metrics__sub" title={criteriaText || undefined}>
          {criteriaHints || criteriaText || 'Not disclosed'}
        </span>
      </div>
    </div>
  );
}
