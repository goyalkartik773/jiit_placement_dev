import { useEffect, useState } from 'react';
import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import { isAbortError } from '../../../services/apiClient';
import { fetchPlacedStudents, type FetchedPlacedStudents } from '../../../services/placementService';
import { formatDate, formatINR } from '../../../utils/format';
import './PlacedStudents.scss';

interface PlacedStudentsProps {
  jobId: string;
}

function ctcLabel(ctcraw: string | null, ctctotal: number | null): string {
  const raw = (ctcraw ?? '').trim();
  return raw || formatINR(ctctotal) || 'Not disclosed';
}

/**
 * Offer students already matched to one job (roll no, name, branch, role,
 * CTC and offer date), loaded on demand from the placed-students endpoint.
 */
export function PlacedStudents({ jobId }: PlacedStudentsProps) {
  const [data, setData] = useState<FetchedPlacedStudents | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);

    fetchPlacedStudents(jobId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught) || controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : 'Could not load the placed students.');
        setLoading(false);
      });

    return () => controller.abort();
  }, [jobId, retryToken]);

  if (loading) {
    return (
      <div className="placed-students" role="status" aria-live="polite">
        <Skeleton width="sm" height="sm" shape="pill" />
        <div className="placed-students__loading-rows">
          <Skeleton width="full" height="sm" />
          <Skeleton width="full" height="sm" />
          <Skeleton width="xl" height="sm" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <p className="placed-students__error" role="alert">
        <Icon name="alert-circle" size={15} />
        <span>{error}</span>
        <Button variant="soft" size="sm" onClick={() => setRetryToken((token) => token + 1)}>
          Retry
        </Button>
      </p>
    );
  }

  const students = data?.students ?? [];

  if (students.length === 0) {
    return <p className="placed-students__empty">No offer students are mapped to this job yet.</p>;
  }

  return (
    <div className="placed-students">
      <p className="placed-students__count" aria-live="polite">
        <strong>{data?.placedCount ?? students.length}</strong> student
        {(data?.placedCount ?? students.length) === 1 ? '' : 's'} matched to{' '}
        <strong>{data?.job.jobprofile}</strong>
      </p>

      <div className="placed-students__scroll">
        <table className="placed-students__table">
          <caption className="sr-only">Students placed through this job</caption>
          <thead>
            <tr>
              <th scope="col">Roll no</th>
              <th scope="col">Student</th>
              <th scope="col">Branch</th>
              <th scope="col">Role</th>
              <th scope="col">CTC</th>
              <th scope="col">Offer date</th>
            </tr>
          </thead>
          <tbody>
            {students.map((student) => (
              <tr key={student.id}>
                <td className="placed-students__roll">{student.rollno}</td>
                <td>
                  <span className="placed-students__name">{student.studentname}</span>
                  {student.email ? <span className="placed-students__email">{student.email}</span> : null}
                </td>
                <td>{student.branch || '-'}</td>
                <td className="placed-students__role">{student.role || '-'}</td>
                <td className="placed-students__ctc">{ctcLabel(student.ctcraw, student.ctctotal)}</td>
                <td>{formatDate(student.placedat)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
