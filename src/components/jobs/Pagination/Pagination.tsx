import { Icon } from '../../common/Icon/Icon';
import './Pagination.scss';

const PAGE_SIZE_OPTIONS = [20, 50, 100];

interface PaginationProps {
  page: number;
  totalPages: number;
  pageSize: number;
  totalCount: number;
  itemCount: number;
  disabled?: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

function pageWindow(page: number, totalPages: number): number[] {
  const pages = new Set<number>([1, totalPages, page - 1, page, page + 1]);
  return [...pages].filter((value) => value >= 1 && value <= totalPages).sort((a, b) => a - b);
}

/** Server-driven pagination controls (page / pageSize come from the API). */
export function Pagination({
  page,
  totalPages,
  pageSize,
  totalCount,
  itemCount,
  disabled = false,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const from = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = (page - 1) * pageSize + itemCount;
  const pages = pageWindow(page, totalPages);
  const canPrev = page > 1 && !disabled;
  const canNext = page < totalPages && !disabled;

  return (
    <nav className="pagination" aria-label="Job list pagination">
      <p className="pagination__summary">
        {totalCount > 0 ? (
          <>
            Showing <strong>{from}–{to}</strong> of <strong>{totalCount}</strong> job{totalCount === 1 ? '' : 's'}
          </>
        ) : (
          'No jobs to show'
        )}
      </p>

      <div className="pagination__controls">
        <label className="pagination__size">
          <span>Per page</span>
          <select value={pageSize} disabled={disabled} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>

        <div className="pagination__pages">
          <button type="button" className="pagination__btn" disabled={!canPrev} onClick={() => onPageChange(page - 1)} aria-label="Previous page">
            <Icon name="chevron-left" size={16} />
          </button>

          {pages.map((value, index) => (
            <span className="pagination__slot" key={value}>
              {index > 0 && value - pages[index - 1] > 1 ? (
                <span className="pagination__ellipsis" aria-hidden="true">
                  …
                </span>
              ) : null}
              <button
                type="button"
                className={`pagination__btn${value === page ? ' is-active' : ''}`}
                aria-current={value === page ? 'page' : undefined}
                disabled={disabled}
                onClick={() => onPageChange(value)}
              >
                {value}
              </button>
            </span>
          ))}

          <button type="button" className="pagination__btn" disabled={!canNext} onClick={() => onPageChange(page + 1)} aria-label="Next page">
            <Icon name="chevron-right" size={16} />
          </button>
        </div>
      </div>
    </nav>
  );
}
