import type { ReactNode } from 'react';
import { Button } from '../Button/Button';
import { StateShell } from '../StateShell/StateShell';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

/** API/network failure view. Retry re-issues the original request. */
export function ErrorState({ title = 'Something went wrong', message, onRetry }: ErrorStateProps) {
  const action: ReactNode = onRetry ? (
    <Button variant="primary" icon="refresh" onClick={onRetry}>
      Try again
    </Button>
  ) : undefined;

  return <StateShell tone="danger" role="alert" icon="alert-circle" title={title} description={message} action={action} />;
}
