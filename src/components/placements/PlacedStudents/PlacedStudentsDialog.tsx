import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { Badge, statusTone } from '../../common/Badge/Badge';
import { Button } from '../../common/Button/Button';
import { CtcChip } from '../../common/CtcChip/CtcChip';
import { EmptyState } from '../../common/EmptyState/EmptyState';
import { Icon } from '../../common/Icon/Icon';
import { Skeleton } from '../../common/Skeleton/Skeleton';
import { Avatar } from '../../ui/Avatar/Avatar';
import { isAbortError } from '../../../services/apiClient';
import { fetchPlacedStudents, type FetchedPlacedStudents } from '../../../services/placementService';
import { StudentProfile } from './StudentProfile';
import { StudentRow } from './StudentRow';
import {
  EMPTY_FILTERS,
  PlacedStudentsFilterBar,
  type PlacedStudentFilters,
} from './PlacedStudentsFilterBar';
import { branchOf, campusOf } from './badgePalette';
import './PlacedStudentsDialog.scss';

interface PlacedStudentsDialogProps {
  /** The job whose offer students are being inspected. */
  job: RosterJob;
  /** The control that opened this — focus returns to it on close. */
  trigger: HTMLElement | null;
  onClose: () => void;
}

/**
 * Only the fields the dialog actually renders. Deliberately a structural
 * subset of BOTH `PlacedJob` (the placed-students feed) and `CompanyJob`
 * (the company-wise feed) so either source can open the roster — they agree
 * on every field except the Superset identifier, which is not shown here.
 */
export interface RosterJob {
  id: string;
  company: string;
  jobprofile: string;
  /** Annual CTC in INR (0 = undisclosed). */
  package: number;
  packageinfo: string;
  location?: string | null;
  status: string;
}

/** Focusable elements the Tab trap cycles through, in DOM order. */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * The placed-students roster for one job, as a MASTER-DETAIL dialog.
 *
 * WHY A DIALOG. The old design nested the table inside the job row, inside
 * the job list, inside the expanded company card — four levels deep — and
 * then opened a 320px drawer *inside* that, squeezing six columns into the
 * leftover ~250px. Nothing had room, and only four of the row's fields ever
 * reached the screen.
 *
 * Research on the pattern (Windows Mail, every CRM roster, the master-detail
 * literature) lands on the same thing: a list you scan on the left, a reading
 * pane for the selected record on the right, and search over the list. Cards
 * are entry points, not destinations — so the row list is a *list* (scanning)
 * and the detail is a real pane (all fields), each doing the job it is good
 * at.
 *
 * This component owns everything: the fetch, the four filters, the selection
 * and focus. Children stay pure.
 *
 * Layout is data-driven, not JS-driven: `data-pane` only matters below
 * `lg`, where the two panes become two screens with a Back button. Above it
 * both are visible and the attribute is inert.
 */
export function PlacedStudentsDialog({ job, trigger, onClose }: PlacedStudentsDialogProps) {
  const [data, setData] = useState<FetchedPlacedStudents | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryToken, setRetryToken] = useState(0);
  const [filters, setFilters] = useState<PlacedStudentFilters>(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pane, setPane] = useState<'list' | 'profile'>('list');

  const panelRef = useRef<HTMLDivElement>(null);

  // ---- data ----------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    setSelectedId(null);
    setFilters(EMPTY_FILTERS);

    fetchPlacedStudents(job.id, controller.signal)
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
  }, [job.id, retryToken]);

  // ---- derived (every hook sits above the returns) -------------------------
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

  // The reading pane always has a record while any row exists: fall back to
  // the first visible row rather than showing an empty right-hand side. A
  // selection that a filter removed is simply dropped, never kept out of view.
  const selectedIdResolved = useMemo(() => {
    if (selectedId && filtered.some((row) => row.id === selectedId)) return selectedId;
    return filtered[0]?.id ?? null;
  }, [filtered, selectedId]);
  const selected = useMemo(
    () => (selectedIdResolved ? filtered.find((row) => row.id === selectedIdResolved) ?? null : null),
    [filtered, selectedIdResolved],
  );

  const patchFilters = useCallback(
    (patch: Partial<PlacedStudentFilters>) => setFilters((prev) => ({ ...prev, ...patch })),
    [],
  );
  const resetFilters = useCallback(() => setFilters(EMPTY_FILTERS), []);

  const select = useCallback((id: string) => {
    setSelectedId(id);
    // Narrow viewports: selecting a row IS navigation to the profile.
    setPane('profile');
  }, []);

  // ---- modal behaviour ------------------------------------------------------
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    // Focus the panel itself first so a screen reader lands in the dialog and
    // announces its name, rather than jumping straight to the close button.
    panelRef.current?.focus();

    return () => {
      document.body.style.overflow = overflow;
      // Return focus to the control that opened us — without this the user is
      // dumped at the top of the document after every inspection. `trigger`
      // is preferred because a mouse click does not reliably leave the button
      // as document.activeElement in every browser; fall back to whatever was
      // focused when the dialog mounted.
      const target =
        trigger && document.contains(trigger) ? trigger : previouslyFocused;
      if (target && typeof target.focus === 'function') target.focus();
    };
  }, [trigger]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;

      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [onClose]);

  // ---- views ---------------------------------------------------------------
  const total = data?.placedCount ?? students.length;
  const title = `Placed students at ${job.company}`;

  const master = (() => {
    if (loading) {
      return (
        <div className="placed-students__loading" role="status" aria-live="polite">
          <Skeleton width="full" height="lg" shape="rect" />
          <Skeleton width="full" height="md" shape="rect" />
          <Skeleton width="full" height="md" shape="rect" />
          <Skeleton width="full" height="md" shape="rect" />
        </div>
      );
    }
    if (error) {
      return (
        <div className="placed-students__error" role="alert">
          <Icon name="alert-circle" size={15} />
          <span>{error}</span>
          <Button variant="soft" size="sm" onClick={() => setRetryToken((t) => t + 1)}>
            Retry
          </Button>
        </div>
      );
    }
    if (students.length === 0) {
      return (
        <EmptyState
          title="No offer students yet"
          description="No offer students are mapped to this job yet."
        />
      );
    }
    if (filtered.length === 0) {
      return (
        <EmptyState
          title="No students match these filters"
          description="Every row was excluded by the current search, branch, campus or batch selection."
          action={
            <Button variant="soft" size="sm" onClick={resetFilters}>
              Clear filters
            </Button>
          }
        />
      );
    }
    return (
      <div className="placed-students__scroll">
        <table className="placed-students__table">
          <caption className="sr-only">Students placed through {job.jobprofile}</caption>
          <thead>
            <tr>
              <th scope="col">Student</th>
              <th scope="col">Branch</th>
              <th scope="col">Role</th>
              <th scope="col" className="placed-students__ctc">
                CTC
              </th>
              <th scope="col">Offer date</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((student) => (
              <StudentRow
                key={student.id}
                student={student}
                selectedId={selectedIdResolved}
                onSelect={select}
              />
            ))}
          </tbody>
        </table>
      </div>
    );
  })();

  return createPortal(
    <div className="placed-students">
      <button type="button" className="placed-students__scrim" aria-label="Close" onClick={onClose} />

      <div
        className="placed-students__panel"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={panelRef}
        tabIndex={-1}
      >
        {/* ----- header: which company, which job, how many ----- */}
        <header className="placed-students__head">
          <Avatar name={job.company} size={42} radius={11} />
          <div className="placed-students__ident">
            <p className="placed-students__eyebrow">Placed students</p>
            <h2 className="placed-students__title">{job.company}</h2>
            <p className="placed-students__meta">
              <Link className="placed-students__joblink" to={`/jobs/${job.id}`}>
                {job.jobprofile}
              </Link>
              {job.location ? (
                <>
                  <span aria-hidden="true"> · </span>
                  <span className="placed-students__place">{job.location}</span>
                </>
              ) : null}
            </p>
          </div>

          <div className="placed-students__head-side">
            <span className="placed-students__facts-inline">
              <CtcChip package={job.package} packageinfo={job.packageinfo} />
              <Badge tone={statusTone(job.status)}>{job.status}</Badge>
            </span>
            <span className="placed-students__count" aria-live="polite">
              <strong>{loading ? '…' : total.toLocaleString()}</strong>
              <span>student{total === 1 ? '' : 's'}</span>
            </span>
            <button type="button" className="placed-students__close" aria-label="Close" onClick={onClose}>
              <Icon name="x" size={17} />
            </button>
          </div>
        </header>

        {/* ----- search + branch / campus / batch, all AND'ed ----- */}
        {!loading && !error && students.length > 0 ? (
          <div className="placed-students__toolbar">
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
          </div>
        ) : null}

        {/* ----- master list | reading pane ----- */}
        <div className="placed-students__body" data-pane={pane}>
          <div className="placed-students__master">{master}</div>
          <aside className="placed-students__detail" aria-label="Student record">
            <StudentProfile student={selected} onBack={() => setPane('list')} />
          </aside>
        </div>
      </div>
    </div>,
    document.body,
  );
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
