import type { ReactNode } from 'react';

interface OverviewItemProps {
  label: string;
  value: ReactNode;
}

/** Single label/value pair inside the overview grid. */
export function OverviewItem({ label, value }: OverviewItemProps) {
  const isEmpty = value === null || value === undefined || value === '';
  return (
    <div className="overview-item">
      <dt className="overview-item__label">{label}</dt>
      <dd className="overview-item__value" title={typeof value === 'string' ? value : undefined}>
        {isEmpty ? <span className="overview-item__empty">Not specified</span> : value}
      </dd>
    </div>
  );
}
