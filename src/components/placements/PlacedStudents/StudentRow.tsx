import { formatDate, initials } from '../../../utils/format';
import { BranchBadge, CampusBadge, RoleBadge } from './StudentBadges';
import { branchOf, campusOf, ctcLabel, shortRoleLabel } from './badgePalette';
import type { PlacedStudent } from '../../../types/dashboard.types';

interface StudentRowProps {
  student: PlacedStudent;
  /** Id of the row whose drawer is open — drives `is-selected` on that one row. */
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/**
 * One row of the matched-students table.
 *
 * Mouse users click anywhere on the row; keyboard users reach the row's name
 * button with Tab and open it with Enter/Space — the row itself is never made
 * a `role="button"`, because that would throw away the table's row semantics.
 * The button stops propagation so one click never fires `onSelect` twice.
 */
export function StudentRow({ student, selectedId, onSelect }: StudentRowProps) {
  const branch = branchOf(student);
  const campus = campusOf(student);
  const role = shortRoleLabel(student);
  const selected = selectedId === student.id;

  const name = (student.studentname ?? '').trim() || 'Unnamed student';
  const roll = (student.rollno ?? '').trim();

  return (
    <tr
      className={`placed-students__row${selected ? ' is-selected' : ''}`}
      onClick={() => onSelect(student.id)}
    >
      <td className="placed-students__person">
        <button
          type="button"
          className="placed-students__open"
          // No aria-label: SC 2.5.3 wants the visible text (name/roll/email)
          // CONTAINED IN the accessible name, and `aria-label="Show details
          // for X"` would replace it. `aria-expanded` is what discloses that
          // this reveals a panel — the standard disclosure-button pattern.
          aria-expanded={selected}
          onClick={(event) => {
            event.stopPropagation();
            onSelect(student.id);
          }}
        >
          <span className="placed-students__avatar" aria-hidden="true">
            {initials(name)}
          </span>
          <span className="placed-students__identity">
            <span className="placed-students__name">{name}</span>
            <span className="placed-students__roll">{roll || '—'}</span>
            {student.email ? <span className="placed-students__email">{student.email}</span> : null}
          </span>
        </button>
      </td>
      <td className="placed-students__badge-cell">
        {branch ? <BranchBadge branch={branch} /> : '-'}
      </td>
      <td className="placed-students__badge-cell">
        {campus ? <CampusBadge campus={campus} /> : '-'}
      </td>
      <td className="placed-students__badge-cell placed-students__role">
        {role ? <RoleBadge role={role} /> : '-'}
      </td>
      <td className="placed-students__ctc">{ctcLabel(student.ctcraw, student.ctctotal)}</td>
      <td className="placed-students__date">{formatDate(student.placedat)}</td>
    </tr>
  );
}
