import type { ReactNode } from 'react';
import { StateShell } from '../StateShell/StateShell';

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}

/** Shown when a query legitimately returns no results. */
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return <StateShell icon="inbox" title={title} description={description} action={action} />;
}
