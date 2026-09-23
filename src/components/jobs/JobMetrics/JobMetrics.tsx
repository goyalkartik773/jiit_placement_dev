import type { JobDetail } from '../../../types/job.types';
import { formatDate, formatINR, formatLpa, formatRelative, isPast } from '../../../utils/format';
import { getCriteriaTone, getPackageTier, type CriteriaTone } from '../../../utils/tiers';
import { MetricCard } from '../MetricCard/MetricCard';
import './JobMetrics.scss';

interface JobMetricsProps {
  job: JobDetail;
}

/** Strictness ladder for picking the strictest criterion on the job. */
const TONE_RANK: Record<CriteriaTone, number> = { unknown: 0, relaxed: 1, moderate: 2, strict: 3 };

const CRITERIA_BADGE_TONE: Record<CriteriaTone, 'rose' | 'emerald' | 'amber' | 'mono'> = {
  strict: 'rose',
  moderate: 'amber',
  relaxed: 'emerald',
  unknown: 'mono',
};

const CRITERIA_ICON_TONE: Record<CriteriaTone, 'rose' | 'emerald' | 'amber' | 'secondary'> = {
  strict: 'rose',
  moderate: 'amber',
  relaxed: 'emerald',
  unknown: 'secondary',
};

/**
 * Bento row of four metric tiles (spec): Registration Closes, Package Pool,
 * Hiring Category, Selection Rules. Tier + strictness color coding is
 * preserved; 0/null values fall back to "Not disclosed".
 */
export function JobMetrics({ job }: JobMetricsProps) {
  const tier = getPackageTier(job.package);
  const lpa = formatLpa(job.package);
  const deadlinePassed = job.deadline ? isPast(job.deadline) : false;
  const deadlineRel = job.deadline ? formatRelative(job.deadline) : null;
  const postedAt = job.posteddatetime ?? job.createdat;

  const marks = Array.isArray(job.eligiblitymarks) ? job.eligiblitymarks.filter(Boolean) : [];
  const criteriaText = marks.map((mark) => mark.criteria).join(' · ');

  let strictest: CriteriaTone | null = null;
  for (const mark of marks) {
    const tone = getCriteriaTone(mark.criteria).tone;
    if (strictest === null || TONE_RANK[tone] > TONE_RANK[strictest]) strictest = tone;
  }

  const deadlineValueClass = [
    'metric-card__value',
    job.deadline ? (deadlinePassed ? 'metric-card__value--rose' : null) : 'metric-card__value--empty',
  ]
    .filter(Boolean)
    .join(' ');

  const packageValueClass = [
    'metric-card__value',
    lpa ? `metric-card__value--${tier.key}` : 'metric-card__value--empty',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="metrics" aria-label="Key job metrics">
      {/* Registration closes */}
      <MetricCard
        icon="calendar"
        label="Registration Closes"
        iconTone={job.deadline ? (deadlinePassed ? 'rose' : 'emerald') : 'secondary'}
        badge={
          job.deadline
            ? { text: deadlinePassed ? 'CLOSED' : 'OPEN', tone: deadlinePassed ? 'rose' : 'emerald' }
            : { text: 'UNKNOWN', tone: 'mono' }
        }
        accent={deadlinePassed ? 'rose' : 'default'}
        footer={{ label: 'Posted', value: postedAt ? formatDate(postedAt) : '—' }}
      >
        <span className={deadlineValueClass} title={job.deadline ? formatDate(job.deadline) : undefined}>
          {job.deadline ? formatDate(job.deadline) : 'Not disclosed'}
        </span>
        {deadlineRel ? <span className="metric-card__sub">{deadlineRel}</span> : null}
      </MetricCard>

      {/* Package pool */}
      <MetricCard
        icon="rupee"
        label="Package Pool"
        iconTone={tier.key}
        badge={lpa ? { text: tier.label, tone: tier.key } : { text: '—', tone: 'mono' }}
        accent="blue"
        footer={{ label: 'Annual CTC', value: formatINR(job.package) ?? '—' }}
      >
        <span className={packageValueClass} title={lpa ? `₹${lpa} per annum · ${tier.range}` : undefined}>
          {lpa ? `₹${lpa}` : 'Not disclosed'}
        </span>
        <span className="metric-card__sub metric-card__sub--mono">{tier.range}</span>
      </MetricCard>

      {/* Hiring category */}
      <MetricCard
        icon="folder"
        label="Hiring Category"
        iconTone="ink"
        badge={job.placementcategorycode ? { text: `CODE ${job.placementcategorycode}`, tone: 'mono' } : undefined}
        footer={{ label: 'Type', value: job.placementtype || '—' }}
      >
        <span className="metric-card__value metric-card__value--sm" title={job.placementcategory || undefined}>
          {job.placementcategory || 'Not disclosed'}
        </span>
      </MetricCard>

      {/* Selection rules */}
      <MetricCard
        icon="checklist"
        label="Selection Rules"
        iconTone={strictest ? CRITERIA_ICON_TONE[strictest] : 'secondary'}
        badge={strictest ? { text: strictest.toUpperCase(), tone: CRITERIA_BADGE_TONE[strictest] } : undefined}
        footer={{
          label: 'Min Criteria',
          value: criteriaText ? <span title={criteriaText}>{criteriaText}</span> : '—',
        }}
      >
        <span
          className={['metric-card__value', marks.length ? null : 'metric-card__value--empty'].filter(Boolean).join(' ')}
          title={criteriaText || undefined}
        >
          {marks.length || '—'}
        </span>
      </MetricCard>
    </div>
  );
}
