import type { JobListItem } from '../../../types/job.types';
import { JobCard } from '../JobCard/JobCard';
import './JobList.scss';

interface JobListProps {
  jobs: JobListItem[];
  /** Dimmed while a refresh request is in flight. */
  refreshing?: boolean;
}

/** Responsive card grid for the job results. */
export function JobList({ jobs, refreshing = false }: JobListProps) {
  return (
    <div className={`job-list${refreshing ? ' is-refreshing' : ''}`} aria-busy={refreshing || undefined}>
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
}
