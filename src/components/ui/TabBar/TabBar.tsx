import { useRef } from 'react';
import type { IconName } from '../../common/Icon/Icon';
import { Icon } from '../../common/Icon/Icon';
import './TabBar.scss';

export interface TabDescriptor {
  /** Stable key; also the suffix of `tab-<id>` / `panel-<id>`. */
  id: string;
  label: string;
  icon?: IconName;
  /** Present in the list but not openable — never receives selection. */
  disabled?: boolean;
  /** Small muted chip trailing the label (e.g. `soon`). */
  badge?: string;
  /** Hover/focus explanation; most useful on a disabled tab. */
  title?: string;
}

interface TabBarProps {
  tabs: TabDescriptor[];
  /** Id of the selected tab. Always one of the enabled ids. */
  value: string;
  onChange: (id: string) => void;
  /** Accessible name for the tablist container itself. */
  label: string;
}

/**
 * Pill tablist: solid accent fill on the active tab, muted track behind.
 *
 * Implements the ARIA tabs pattern properly — `role="tablist"` / `role="tab"`,
 * one roving `tabIndex` (the selected tab), `aria-controls` pointing at the
 * rendered panel, and arrow / Home / End navigation.
 *
 * Activation is AUTOMATIC (moving focus selects) because every panel here is
 * already in memory, which is what APG recommends in that case. A disabled tab
 * is still focusable — so keyboard and screen-reader users can discover it and
 * read its `title` — but focusing it deliberately does NOT select it.
 *
 * Callers render the matching `id={`panel-${tab.id}`}` with `role="tabpanel"`.
 */
export function TabBar({ tabs, value, onChange, label }: TabBarProps) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  /** Focus one tab and, unless it is disabled, select it too. */
  const focusIndex = (index: number) => {
    const tab = tabs[index];
    if (!tab) return;
    refs.current[tab.id]?.focus();
    if (!tab.disabled && tab.id !== value) onChange(tab.id);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, id: string) => {
    const index = tabs.findIndex((tab) => tab.id === id);
    if (index < 0) return;
    switch (event.key) {
      case 'ArrowRight':
        event.preventDefault();
        focusIndex((index + 1) % tabs.length);
        break;
      case 'ArrowLeft':
        event.preventDefault();
        focusIndex((index - 1 + tabs.length) % tabs.length);
        break;
      case 'Home':
        event.preventDefault();
        focusIndex(0);
        break;
      case 'End':
        event.preventDefault();
        focusIndex(tabs.length - 1);
        break;
      default:
        break;
    }
  };

  return (
    <div className="ui-tabbar" role="tablist" aria-label={label}>
      {tabs.map((tab) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(node) => {
              refs.current[tab.id] = node;
            }}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={tab.disabled ? undefined : `panel-${tab.id}`}
            aria-disabled={tab.disabled || undefined}
            tabIndex={selected ? 0 : -1}
            title={tab.title}
            className="ui-tabbar__tab"
            onClick={() => {
              if (!tab.disabled) onChange(tab.id);
            }}
            onKeyDown={(event) => onKeyDown(event, tab.id)}
          >
            {tab.icon ? <Icon name={tab.icon} size={15} className="ui-tabbar__icon" /> : null}
            <span className="ui-tabbar__label">{tab.label}</span>
            {tab.badge ? <span className="ui-tabbar__badge">{tab.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
