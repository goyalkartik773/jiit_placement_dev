import { Button } from '../../common/Button/Button';
import { Icon, type IconName } from '../../common/Icon/Icon';
import type { JobFilters, SortKey } from '../../../utils/jobList';
import './JobsToolbar.scss';

interface JobsToolbarProps {
  searchInput: string;
  onSearchChange: (value: string) => void;
  filters: JobFilters;
  onFiltersChange: (patch: Partial<JobFilters>) => void;
  onClearFilters: () => void;
  filtersActive: boolean;
  /** Refinement controls only apply when the complete result set is loaded. */
  refineAvailable: boolean;
  options: { locations: string[]; statuses: string[]; categories: string[] };
}

type FilterKey = 'location' | 'status' | 'category' | 'sort';
type FilterTone = 'accent' | 'green' | 'red';

interface FilterOption {
  value: string;
  label: string;
}

/**
 * Colour follows the MEANING of the selection, never its position:
 * status "Active" is the positive/eligible case (green), any other status is
 * restrictive (red), every other selection is the neutral primary choice
 * (accent). Unselected options of a group are all identical neutral gray.
 */
function toneFor(key: FilterKey, value: string): FilterTone {
  if (key === 'status' && value) return value.toLowerCase() === 'active' ? 'green' : 'red';
  return 'accent';
}

interface FilterGroupProps {
  group: FilterKey;
  label: string;
  icon: IconName;
  options: FilterOption[];
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}

/**
 * One filter group in the single toolbar row.
 *
 * Every group is a select with an icon and no visible caption. They used to be
 * pill buttons whenever a group had five options or fewer, then carried an
 * uppercase "LOCATION"-style label beside the control — which cost ~60px per
 * group and put Sort on a second row. The label was redundant: each select's
 * own option text already names the dimension ("All locations", "All
 * statuses"), so the icon carries the group and the select carries the value.
 * The only group whose options don't name their dimension is Sort, which is
 * why it keeps the `sort` glyph. `aria-label` still names every control.
 *
 * Same meaning-based tint on the selected state
 * (`jobs-toolbar__select--{tone}`); wrapping only when the viewport genuinely
 * cannot hold search, four filters and Clear.
 */
function FilterGroup({ group, label, icon, options, value, disabled, onChange }: FilterGroupProps) {
  return (
    <div className="jobs-toolbar__group">
      <span className="jobs-toolbar__group-icon" aria-hidden="true">
        <Icon name={icon} size={15} />
      </span>

      <span className={`jobs-toolbar__select jobs-toolbar__select--${toneFor(group, value)}`}>
        <select
          aria-label={label}
          title={label}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option.value || 'all'} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </span>
    </div>
  );
}

/** Search (server-side) + refinement controls (client-side over the full set). */
export function JobsToolbar({
  searchInput,
  onSearchChange,
  filters,
  onFiltersChange,
  onClearFilters,
  filtersActive,
  refineAvailable,
  options,
}: JobsToolbarProps) {
  const locationOptions: FilterOption[] = [
    { value: '', label: 'All locations' },
    ...options.locations.map((location) => ({ value: location, label: location })),
  ];
  const statusOptions: FilterOption[] = [
    { value: '', label: 'All statuses' },
    ...options.statuses.map((status) => ({ value: status, label: status })),
  ];
  const categoryOptions: FilterOption[] = [
    { value: '', label: 'All categories' },
    ...options.categories.map((category) => ({ value: category, label: category })),
  ];
  const sortOptions: FilterOption[] = [
    { value: 'newest', label: 'Newest first' },
    { value: 'oldest', label: 'Oldest first' },
    { value: 'title-asc', label: 'Title A–Z' },
    { value: 'package-desc', label: 'Package: high to low' },
  ];

  return (
    <section className="jobs-toolbar" aria-label="Search and filter jobs">
      <div className="jobs-toolbar__field">
        <span className="jobs-toolbar__search-icon" aria-hidden="true">
          <Icon name="search" size={17} />
        </span>
        <input
          type="search"
          value={searchInput}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search job title or company…"
          aria-label="Search jobs by title or company"
        />
        {searchInput ? (
          <button type="button" className="jobs-toolbar__clear" onClick={() => onSearchChange('')} aria-label="Clear search">
            <Icon name="x" size={14} />
          </button>
        ) : null}
      </div>

      <FilterGroup
        group="location"
        label="Location"
        icon="pin"
        options={locationOptions}
        value={filters.location}
        disabled={!refineAvailable}
        onChange={(value) => onFiltersChange({ location: value })}
      />

      <FilterGroup
        group="status"
        label="Status"
        icon="check-circle"
        options={statusOptions}
        value={filters.status}
        disabled={!refineAvailable}
        onChange={(value) => onFiltersChange({ status: value })}
      />

      <FilterGroup
        group="category"
        label="Category"
        icon="tag"
        options={categoryOptions}
        value={filters.category}
        disabled={!refineAvailable}
        onChange={(value) => onFiltersChange({ category: value })}
      />

      <FilterGroup
        group="sort"
        label="Sort"
        icon="sort"
        options={sortOptions}
        value={filters.sort}
        disabled={!refineAvailable}
        onChange={(value) => onFiltersChange({ sort: value as SortKey })}
      />

      {filtersActive ? (
        <Button variant="ghost" size="sm" icon="x" onClick={onClearFilters} className="jobs-toolbar__clear-filters">
          Clear
        </Button>
      ) : null}
    </section>
  );
}
