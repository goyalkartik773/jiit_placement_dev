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
  icon?: IconName;
  options: FilterOption[];
  value: string;
  disabled: boolean;
  /** Compact sets render as pill buttons; long lists stay one pill-shaped select. */
  mode: 'pills' | 'select';
  onChange: (value: string) => void;
}

/** One labelled filter group; groups are separated by a hairline divider. */
function FilterGroup({ group, label, icon, options, value, disabled, mode, onChange }: FilterGroupProps) {
  return (
    <div className="jobs-toolbar__group">
      <span className="jobs-toolbar__group-label">
        {icon ? <Icon name={icon} size={14} /> : null}
        {label}
      </span>

      {mode === 'pills' ? (
        <div className="jobs-toolbar__pills">
          {options.map((option) => {
            const selected = option.value === value;
            const tone = toneFor(group, option.value);
            return (
              <button
                key={option.value || 'all'}
                type="button"
                className={[
                  'jobs-toolbar__pill',
                  selected ? 'jobs-toolbar__pill--selected' : '',
                  selected ? `jobs-toolbar__pill--${tone}` : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                aria-pressed={selected}
                disabled={disabled}
                onClick={() => onChange(option.value)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      ) : (
        <span className={`jobs-toolbar__select jobs-toolbar__select--${toneFor(group, value)}`}>
          <select
            aria-label={label}
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
      )}
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

  // Values lists can grow with the data (locations especially) — past this
  // point one pill per value would become a wall, so the group keeps a single
  // compact pill-shaped select with exactly the same options inside it.
  const modeFor = (optionCount: number): 'pills' | 'select' => (optionCount <= 5 ? 'pills' : 'select');

  return (
    <section className="jobs-toolbar" aria-label="Search and filter jobs">
      <div className="jobs-toolbar__search">
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

        {filtersActive ? (
          <Button variant="ghost" size="sm" icon="x" onClick={onClearFilters} className="jobs-toolbar__clear-filters">
            Clear
          </Button>
        ) : null}
      </div>

      <div className="jobs-toolbar__filters">
        <span className="jobs-toolbar__filters-label">
          <Icon name="layers" size={15} />
          Filters
        </span>

        <FilterGroup
          group="location"
          label="Location"
          mode="select"
          options={locationOptions}
          value={filters.location}
          disabled={!refineAvailable}
          onChange={(value) => onFiltersChange({ location: value })}
        />

        <FilterGroup
          group="status"
          label="Status"
          mode={modeFor(statusOptions.length)}
          options={statusOptions}
          value={filters.status}
          disabled={!refineAvailable}
          onChange={(value) => onFiltersChange({ status: value })}
        />

        <FilterGroup
          group="category"
          label="Category"
          mode={modeFor(categoryOptions.length)}
          options={categoryOptions}
          value={filters.category}
          disabled={!refineAvailable}
          onChange={(value) => onFiltersChange({ category: value })}
        />

        <FilterGroup
          group="sort"
          label="Sort"
          icon="sort"
          mode="pills"
          options={sortOptions}
          value={filters.sort}
          disabled={!refineAvailable}
          onChange={(value) => onFiltersChange({ sort: value as SortKey })}
        />
      </div>
    </section>
  );
}
