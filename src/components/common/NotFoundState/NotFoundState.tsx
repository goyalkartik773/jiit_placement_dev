import type { ReactNode } from 'react';
import { StateShell } from '../StateShell/StateShell';

interface NotFoundStateProps {
  title?: string;
  description?: string;
  action?: ReactNode;
}

/** Job could not be found (API 404). */
export function NotFoundState({ title = 'Job not found', description, action }: NotFoundStateProps) {
  return <StateShell icon="search" title={title} description={description} action={action} />;
}
