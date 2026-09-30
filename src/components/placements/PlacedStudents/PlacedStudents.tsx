import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '../../common/Button/Button';
import { EmptyState } from '../../common/EmptyState/EmptyState';
import { Icon } from '../../common/Icon/Icon';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import { isAbortError } from '../../../services/apiClient';
import { fetchPlacedStudents, type FetchedPlacedStudents } from '../../../services/placementService';
import { StudentDetailDrawer } from './StudentDetailDrawer';
import { StudentRow } from './StudentRow';
import {
  EMPTY_FILTERS,
  PlacedStudentsFilterBar,
  type PlacedStudentFilters,
} from './PlacedStudentsFilterBar';
import { branchOf, campusOf } from './badgePalette';
import './PlacedStudents.scss';

interface PlacedStudentsProps {
  jobId: string;
}

/** Non-empty, de-duplicated, alphabetised options for one filter select. */
function collectOptions(values: (string | null | undefined)[]): string[] {
  const set = new Set<string>();
  for (const value of values) {
    const trimmed = (value ?? '').trim();
    if (trimmed) set.add(trimmed);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}

/** Batch years sort numerically (2021 before 2022), unlike the text options. */
function collectBatches(values: (number | null | undefined)[]): string[] {
  const set = new Set<number>();
  for (const value of values) if (typeof value === 'number' && value > 0) set.add(value);
  return [...set].sort((a, b) => a - b).map(String);
}

/**
 * Offer students already matched to one job (roll no, name, branch, role,
 * CTC and offer date), loaded on demand from the placed-students endpoint.
 *
 * This component owns ALL of this screen's state: the fetched rows, the four
 * filter values and which row's drawer is open. The table and the drawer are
 * pure children — they receive data and callbacks, never fetch or mutate.
 */
export function PlacedStudents({ jobId }: PlacedStudentsProps) {
  const [data, setData] = useState<FetchedPlacedStudents | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryToken, setRetryToken] = useState(0);

  const [filters, setFilters] = useState<PlacedStudentFilters>(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    // A different job has a different row set — an id from the old one would
    // either vanish or, worse, match an unrelated student.
    setSelectedId(null);
    setFilters(EMPTY_FILTERS);

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

  // ---- derived (every hook sits above the early returns) ------------------
  const students = useMemo(() => data?.students ?? [], [data]);

  const branches = useMemo(() => collectOptions(students.map(branchOf)), [students]);
  const campuses = useMemo(() => collectOptions(students.map(campusOf)), [students]);
  const batches = useMemo(() => collectBatches(students.map((s) => s.batchyear)), [students]);

  const filtered = useMemo(() => {
    const query = filters.search.trim().toLowerCase();
    return students.filter((student) => {
      if (filters.branch && branchOf(student) !== filters.branch) return false;
      if (filters.campus && campusOf(student) !== filters.campus) return false;
      if (filters.batch && String(student.batchyear ?? '') !== filters.batch) return false;
      if (query) {
        const haystack =
          `${student.studentname ?? ''} ${student.rollno ?? ''} ${student.email ?? ''}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [students, filters]);

  // Filtering never closes an open drawer: it is a detail panel, not a
  // dropdown. Only an explicit close or a job switch dismisses it.
  const selected = useMemo(
    () => (selectedId ? students.find((student) => student.id === selectedId) ?? null : null),
    [students, selectedId],
  );

  const closeDrawer = useCallback(() => setSelectedId(null), []);
  const patchFilters = useCallback(
    (patch: Partial<PlacedStudentFilters>) => setFilters((prev) => ({ ...prev, ...patch })),
    [],
  );
  const resetFilters = useCallback(() => setFilters(EMPTY_FILTERS), []);

  // ---- early views --------------------------------------------------------
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

  if (students.length === 0) {
    return <p className="placed-students__empty">No offer students are mapped to this job yet.</p>;
  }

  const total = data?.placedCount ?? students.length;

  return (
    <div className="placed-students">
      <p className="placed-students__count" aria-live="polite">
        <strong>{total}</strong> student{total === 1 ? '' : 's'} matched to{' '}
        <strong>{data?.job.jobprofile ?? 'this job'}</strong>
      </p>

      <PlacedStudentsFilterBar
        value={filters}
        onChange={patchFilters}
        onReset={resetFilters}
        branches={branches}
        campuses={campuses}
        batches={batches}
        shown={filtered.length}
        total={students.length}
      />

      <div className="placed-students__layout">
        <div className="placed-students__main">
          {filtered.length === 0 ? (
            <EmptyState
              title="No students match these filters"
              description="Every row was excluded by the current search, branch, campus or batch selection."
              action={
                <Button variant="soft" size="sm" onClick={resetFilters}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <div className="placed-students__scroll">
              <table className="placed-students__table">
                <caption className="sr-only">Students placed through this job</caption>
                <thead>
                  <tr>
                    <th scope="col">Student</th>
                    <th scope="col">Branch</th>
                    <th scope="col">Campus</th>
                    <th scope="col">Role</th>
                    <th scope="col" className="placed-students__ctc">CTC</th>
                    <th scope="col">Offer date</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((student) => (
                    <StudentRow
                      key={student.id}
                      student={student}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Mobile-only backdrop (display:none from `lg` up) */}
        {selected ? (
          <button
            type="button"
            className="student-drawer__scrim"
            aria-label="Close"
            onClick={closeDrawer}
          />
        ) : null}

        <StudentDetailDrawer student={selected} onClose={closeDrawer} />
      </div>
    </div>
  );
}
