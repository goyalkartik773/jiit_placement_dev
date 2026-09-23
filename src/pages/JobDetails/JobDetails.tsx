import { useParams } from 'react-router-dom';
import { ButtonLink } from '../../components/common/Button/Button';
import { ErrorState } from '../../components/common/ErrorState/ErrorState';
import { NotFoundState } from '../../components/common/NotFoundState/NotFoundState';
import { JobDescription } from '../../components/jobs/JobDescription/JobDescription';
import { JobDocuments } from '../../components/jobs/JobDocuments/JobDocuments';
import { JobHeader } from '../../components/jobs/JobHeader/JobHeader';
import { JobMetrics } from '../../components/jobs/JobMetrics/JobMetrics';
import { JobOverview } from '../../components/jobs/JobOverview/JobOverview';
import { JobRequirements } from '../../components/jobs/JobRequirements/JobRequirements';
import { JobSelectionProcess } from '../../components/jobs/JobSelectionProcess/JobSelectionProcess';
import { JobDetailsSkeleton } from './JobDetailsSkeleton';
import { useJobDetails } from '../../hooks/useJobDetails';
import './JobDetails.scss';

/**
 * Job details page (container).
 *
 * Spec layout: breadcrumb bar + hero, a 4-tile metric bento, then an 8/4
 * split — main column (description / qualifications / process) beside a
 * sidebar (documents / overview) that stacks below the main column under
 * 1080px. Every value comes from GET /api/jobs/{id}.
 */
export function JobDetails() {
  const { jobId } = useParams<{ jobId: string }>();
  const { job, loading, error, notFound, reload } = useJobDetails(jobId);

  if (loading) {
    return (
      <div className="page page--detail">
        <JobDetailsSkeleton />
      </div>
    );
  }

  if (error && !job && !notFound) {
    return (
      <div className="page page--detail">
        <ErrorState title="Could not load this job" message={error.message} onRetry={reload} />
      </div>
    );
  }

  if (notFound || !job) {
    return (
      <div className="page page--detail">
        <NotFoundState
          description={notFound ? 'This job does not exist in the placement database.' : 'The job could not be loaded.'}
          action={
            <ButtonLink to="/" variant="primary" icon="arrow-left">
              Browse all jobs
            </ButtonLink>
          }
        />
      </div>
    );
  }

  return (
    <div className="page page--detail">
      <JobHeader job={job} />
      <JobMetrics job={job} />

      <div className="detail-split">
        <div className="detail-split__main">
          <JobDescription job={job} />
          <JobRequirements job={job} />
          <JobSelectionProcess job={job} />
        </div>

        <aside className="detail-split__side" aria-label="Documents and job overview">
          <JobDocuments jobId={job.id} documents={job.documents} />
          <JobOverview job={job} />
        </aside>
      </div>
    </div>
  );
}
