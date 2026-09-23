import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
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

/** Search (server-side) + refinement selects (client-side over the full set). */
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
  return (
    <section className="jobs-toolbar" aria-label="Search and filter jobs">
      <div className="jobs-toolbar__search">
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

      <div className="jobs-toolbar__filters">
        <span className="jobs-toolbar__filters-label">
          <Icon name="layers" size={15} />
          Filters
        </span>

        <label className="jobs-toolbar__select">
          <span>Location</span>
          <select
            value={filters.location}
            disabled={!refineAvailable}
            onChange={(event) => onFiltersChange({ location: event.target.value })}
          >
            <option value="">All locations</option>
            {options.locations.map((location) => (
              <option key={location} value={location}>
                {location}
              </option>
            ))}
          </select>
        </label>

        <label className="jobs-toolbar__select">
          <span>Status</span>
          <select value={filters.status} disabled={!refineAvailable} onChange={(event) => onFiltersChange({ status: event.target.value })}>
            <option value="">All statuses</option>
            {options.statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>

        <label className="jobs-toolbar__select">
          <span>Category</span>
          <select
            value={filters.category}
            disabled={!refineAvailable}
            onChange={(event) => onFiltersChange({ category: event.target.value })}
          >
            <option value="">All categories</option>
            {options.categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>

        <label className="jobs-toolbar__select jobs-toolbar__select--sort">
          <span>
            <Icon name="sort" size={14} />
            Sort
          </span>
          <select
            value={filters.sort}
            disabled={!refineAvailable}
            onChange={(event) => onFiltersChange({ sort: event.target.value as SortKey })}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="title-asc">Title A–Z</option>
            <option value="package-desc">Package: high to low</option>
          </select>
        </label>

        {filtersActive ? (
          <Button variant="ghost" size="sm" icon="x" onClick={onClearFilters}>
            Clear
          </Button>
        ) : null}

        {!refineAvailable ? (
          <span
            className="jobs-toolbar__hint"
            title="Refinement runs on the complete result set. The API caps a page at 100 jobs — raise “Per page” or search to load everything."
          >
            <Icon name="info" size={14} />
            Refine unlocks when all results are loaded
          </span>
        ) : null}
      </div>
    </section>
  );
}
