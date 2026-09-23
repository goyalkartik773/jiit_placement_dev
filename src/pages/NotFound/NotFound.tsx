import { ButtonLink } from '../../components/common/Button/Button';
import { NotFoundState } from '../../components/common/NotFoundState/NotFoundState';
import './NotFound.scss';

/** Catch-all route. */
export function NotFound() {
  return (
    <div className="page not-found">
      <NotFoundState
        title="Page not found"
        description="The page you are looking for does not exist or may have been moved."
        action={
          <ButtonLink to="/" variant="primary" icon="arrow-left">
            Back to jobs
          </ButtonLink>
        }
      />
    </div>
  );
}
