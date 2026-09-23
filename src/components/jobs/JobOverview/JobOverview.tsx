import type { JobDetail } from '../../../types/job.types';
import { formatDate, formatDateTime, isPast } from '../../../utils/format';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { CtcChip } from '../../common/CtcChip/CtcChip';
import { Panel } from '../../common/Panel/Panel';
import { OverviewItem } from './OverviewItem';
import './JobOverview.scss';

interface JobOverviewProps {
  job: JobDetail;
}

/**
 * Drive metadata sidebar card (spec): right-aligned label/value rows for
 * the top-level jobs-table columns, with dividers between rows.
 */
export function JobOverview({ job }: JobOverviewProps) {
  const deadlinePassed = isPast(job.deadline);

  return (
    <Panel icon="briefcase" title="Job Overview" size="sm">
      <dl className="meta-list">
        <OverviewItem
          label="Job status"
          value={
            <Badge tone={statusTone(job.status)} dot>
              {job.status || 'Unknown'}
            </Badge>
          }
        />
        <OverviewItem label="Recruiter entity" value={job.company} />
        <OverviewItem label="Location" value={job.location} />
        <OverviewItem
          label="Compensation"
          value={<CtcChip package={job.package} packageinfo={job.packageinfo} size="sm" showTierWord />}
        />
        <OverviewItem label="Placement category" value={job.placementcategory} />
        <OverviewItem label="Placement type" value={job.placementtype} />
        <OverviewItem
          label="Application deadline"
          value={
            job.deadline ? (
              <span className="meta-list__deadline">
                {formatDate(job.deadline)}
                {deadlinePassed ? ' (Passed)' : ''}
              </span>
            ) : null
          }
        />
        <OverviewItem
          label="Notice published"
          value={job.posteddatetime ? <span className="meta-list__mono">{formatDateTime(job.posteddatetime)}</span> : null}
        />
        <OverviewItem
          label="Drive setup"
          value={job.createdat ? <span className="meta-list__mono">{formatDateTime(job.createdat)}</span> : null}
        />
      </dl>
    </Panel>
  );
}
