import { Icon } from '../../common/Icon/Icon';
import { SearchField } from '../../common/SearchField/SearchField';

export interface PlacedStudentFilters {
  search: string;
  branch: string;
  campus: string;
  batch: string;
}

export const EMPTY_FILTERS: PlacedStudentFilters = { search: '', branch: '', campus: '', batch: '' };

interface PlacedStudentsFilterBarProps {
  value: PlacedStudentFilters;
  /** Partial patch — the parent owns the state, this only proposes changes. */
  onChange: (patch: Partial<PlacedStudentFilters>) => void;
  onReset: () => void;
  branches: string[];
  campuses: string[];
  batches: string[];
  /** Rows left after filtering. */
  shown: number;
  /** Rows before filtering. */
  total: number;
}

interface SelectProps {
  label: string;
  allLabel: string;
  options: string[];
  selected: string;
  onChange: (value: string) => void;
}

function FilterSelect({ label, allLabel, options, selected, onChange }: SelectProps) {
  return (
    <label className="placed-students__filter">
      <span className="sr-only">{label}</span>
      <select value={selected} onChange={(event) => onChange(event.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <Icon name="chevron-down" size={14} className="placed-students__filter-caret" />
    </label>
  );
}

/**
 * Search + branch / campus / batch selects sitting directly above the table.
 *
 * The list is a single company's matches (88 for Infosys, 232 at the very
 * most), so filtering runs synchronously on every keystroke — no debounce
 * layer is worth its latency budget at this size.
 *
 * The three selects are plain AND conditions; an option that would match
 * nothing under the other two is still offered, and the empty state below
 * explains why nothing is left.
 */
export function PlacedStudentsFilterBar({
  value,
  onChange,
  onReset,
  branches,
  campuses,
  batches,
  shown,
  total,
}: PlacedStudentsFilterBarProps) {
  const dirty =
    value.search !== '' || value.branch !== '' || value.campus !== '' || value.batch !== '';

  return (
    <div className="placed-students__filters">
      <div className="placed-students__filters-row">
        <div className="placed-students__filters-search">
          <SearchField
            label="Search students by name, roll number or email"
            placeholder="Search name, roll no or email"
            value={value.search}
            onChange={(search) => onChange({ search })}
          />
        </div>

        <div className="placed-students__filters-selects">
          <FilterSelect
            label="Filter by branch"
            allLabel="All branches"
            options={branches}
            selected={value.branch}
            onChange={(branch) => onChange({ branch })}
          />
          <FilterSelect
            label="Filter by campus"
            allLabel="All campuses"
            options={campuses}
            selected={value.campus}
            onChange={(campus) => onChange({ campus })}
          />
          <FilterSelect
            label="Filter by batch year"
            allLabel="All batches"
            options={batches}
            selected={value.batch}
            onChange={(batch) => onChange({ batch })}
          />
        </div>

        {dirty ? (
          <button type="button" className="placed-students__filters-reset" onClick={onReset}>
            <Icon name="x" size={13} />
            <span>Reset</span>
          </button>
        ) : null}
      </div>

      <p className="placed-students__filters-meta" aria-live="polite">
        {shown === total
          ? `${total} student${total === 1 ? '' : 's'}`
          : `Showing ${shown} of ${total} students`}
      </p>
    </div>
  );
}
