import { Icon } from '../Icon/Icon';
import './SearchField.scss';

interface SearchFieldProps {
  value: string;
  onChange: (value: string) => void;
  /** Accessible name of the input (also used as its label text for SR). */
  label: string;
  placeholder: string;
  id?: string;
}

/**
 * Labelled search input with a leading magnifier and a clear button.
 * The parent owns the value; debouncing is the caller's decision.
 */
export function SearchField({ value, onChange, label, placeholder, id }: SearchFieldProps) {
  return (
    <div className="search-field">
      <span className="search-field__icon" aria-hidden="true">
        <Icon name="search" size={17} />
      </span>
      <input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={label}
      />
      {value ? (
        <button type="button" className="search-field__clear" onClick={() => onChange('')} aria-label="Clear search">
          <Icon name="x" size={14} />
        </button>
      ) : null}
    </div>
  );
}
