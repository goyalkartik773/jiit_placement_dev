import { useEffect, useRef } from 'react';
import { Icon } from '../../common/Icon/Icon';
import { formatDate, initials } from '../../../utils/format';
import { BranchBadge, CampusBadge, RoleBadge } from './StudentBadges';
import { branchOf, campusOf, ctcLabel, shortRoleLabel } from './badgePalette';
import type { PlacedStudent } from '../../../types/dashboard.types';
import './StudentDetailDrawer.scss';

interface StudentDetailDrawerProps {
  /** The row whose detail is showing. `null` collapses the drawer. */
  student: PlacedStudent | null;
  onClose: () => void;
}

interface TimelineStep {
  label: string;
  /** ISO timestamp straight from the row, or null when unknown. */
  at: string | null;
}

/**
 * Steps the client can actually derive.
 *
 * `shortlist_events` is never exposed — the API only serves
 * `/api/placements/company-wise` and `/api/placements/jobs/{id}/placed-students`,
 * and neither returns shortlist rows. So "Shortlisted" and "Interview cleared"
 * are intentionally absent; they appear the day the backend puts a shortlist
 * field on this response. Do NOT invent them client-side.
 */
function timelineSteps(student: PlacedStudent): TimelineStep[] {
  const steps: TimelineStep[] = [];
  const released = student.offerreceivedat ?? student.placedat ?? null;
  if (released) steps.push({ label: 'Offer released', at: released });
  return steps;
}

/**
 * Right-hand detail drawer for one matched student.
 *
 * Always mounted so its width can transition: collapsed it is 0px wide with
 * overflow hidden, open it is 320px. Selecting a SECOND row swaps `student`
 * while the drawer stays open — it never unmounts, so there is no
 * close-then-reopen flash. Below `lg` the CSS turns it into a fixed bottom
 * sheet with a scrim.
 */
export function StudentDetailDrawer({ student, onClose }: StudentDetailDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const open = Boolean(student);

  // Escape closes the drawer from anywhere on the page.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  // Focus moves to Close only on the 0 -> 1 transition; picking another row
  // while open re-renders the content without stealing focus again. On close,
  // focus leaves the button before it drops inside an aria-hidden subtree.
  useEffect(() => {
    if (open) {
      closeRef.current?.focus();
    } else if (document.activeElement === closeRef.current) {
      closeRef.current?.blur();
    }
  }, [open]);

  const name = student ? ((student.studentname ?? '').trim() || 'Unnamed student') : '';
  const roll = student ? (student.rollno ?? '').trim() : '';
  const branch = student ? branchOf(student) : null;
  const campus = student ? campusOf(student) : null;
  const roleShort = student ? shortRoleLabel(student) : null;
  const roleFull = student
    ? (student.rolelevel ?? '').trim() || (student.role ?? '').trim()
    : '';
  const batch = student?.batchyear ?? null;
  const steps = student ? timelineSteps(student) : [];
  const chips = [branch, campus, roleShort].filter((chip): chip is string => Boolean(chip));

  return (
    <aside
      className={`student-drawer${open ? ' is-open' : ''}`}
      role="dialog"
      aria-label="Student details"
      aria-hidden={!open}
    >
      <div className="student-drawer__inner">
        <header className="student-drawer__head">
          <span className="student-drawer__avatar" aria-hidden="true">
            {open ? initials(name) : ''}
          </span>
          <div className="student-drawer__ident">
            <p className="student-drawer__eyebrow">Student details</p>
            {/* While collapsed the whole aside is aria-hidden; leaving the
                placeholders empty keeps a stray "—" out of the heading tree. */}
            <h4 className="student-drawer__title">{open ? name : ''}</h4>
            <p className="student-drawer__roll">{open ? roll : ''}</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="student-drawer__close"
            aria-label="Close"
            onClick={onClose}
            tabIndex={open ? 0 : -1}
          >
            <Icon name="x" size={16} />
          </button>
        </header>

        {student ? (
          <div className="student-drawer__body">
            <dl className="student-drawer__facts">
              <div className="student-drawer__fact">
                <dt>Company</dt>
                <dd>{(student.companyname ?? '').trim() || '—'}</dd>
              </div>
              <div className="student-drawer__fact">
                <dt>CTC</dt>
                <dd className="student-drawer__ctc">{ctcLabel(student.ctcraw, student.ctctotal)}</dd>
              </div>
              {roleFull ? (
                <div className="student-drawer__fact">
                  <dt>Role</dt>
                  <dd>{roleFull}</dd>
                </div>
              ) : null}
              <div className="student-drawer__fact">
                <dt>Offer date</dt>
                <dd>{formatDate(student.offerreceivedat ?? student.placedat)}</dd>
              </div>
              {batch ? (
                <div className="student-drawer__fact">
                  <dt>Batch year</dt>
                  <dd>{batch}</dd>
                </div>
              ) : null}
            </dl>

            {/* Every chip has a text label; an unknown value never renders as "undefined". */}
            {chips.length > 0 ? (
              <section className="student-drawer__section" aria-label="Classifications">
                <h5 className="student-drawer__section-title">Classifications</h5>
                <ul className="student-drawer__chips">
                  {branch ? (
                    <li>
                      <BranchBadge branch={branch} />
                    </li>
                  ) : null}
                  {campus ? (
                    <li>
                      <CampusBadge campus={campus} />
                    </li>
                  ) : null}
                  {roleShort ? (
                    <li>
                      <RoleBadge role={roleShort} />
                    </li>
                  ) : null}
                </ul>
              </section>
            ) : null}

            {/* A one-point "timeline" is noise (the offer date is already a fact
                above), so the section only renders once 2+ steps are derivable. */}
            {steps.length >= 2 ? (
              <section className="student-drawer__section" aria-label="Timeline">
                <h5 className="student-drawer__section-title">Timeline</h5>
                <ol className="student-drawer__timeline">
                  {steps.map((step) => (
                    <li key={step.label} className="student-drawer__step">
                      <span className="student-drawer__dot" aria-hidden="true" />
                      <span className="student-drawer__step-label">{step.label}</span>
                      <span className="student-drawer__step-at">{formatDate(step.at)}</span>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
