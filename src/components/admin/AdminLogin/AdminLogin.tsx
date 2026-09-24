import { useState, type FormEvent } from 'react';
import { Button } from '../../common/Button/Button';
import { Icon } from '../../common/Icon/Icon';
import { ApiError, isAbortError } from '../../../services/apiClient';
import { adminLogin } from '../../../services/adminService';
import './AdminLogin.scss';

interface AdminLoginProps {
  /** Receives the fresh session token; the parent flips into the console view. */
  onLogin: (token: string) => void;
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError && error.httpStatus === 401) {
    return 'Invalid username or password.';
  }
  return error instanceof Error ? error.message : 'Sign-in failed. Please try again.';
}

/** Credential form for the admin console. Presentation only — auth lives in adminService. */
export function AdminLogin({ onLogin }: AdminLoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (submitting) return;

    const trimmedUser = username.trim();
    if (!trimmedUser || !password) {
      setError('Enter both your username and password.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      onLogin(await adminLogin(trimmedUser, password));
    } catch (submitError: unknown) {
      if (!isAbortError(submitError)) setError(messageOf(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="admin-login">
      <section className="admin-login__card" aria-labelledby="admin-login-title">
        <span className="admin-login__mark" aria-hidden="true">
          <Icon name="terminal" size={20} />
        </span>
        <p className="admin-login__eyebrow">JIIT Placement</p>
        <h1 id="admin-login-title" className="admin-login__title">
          Admin sign in
        </h1>
        <p className="admin-login__subtitle">Restricted console — job synchronization and database counts.</p>

        <form className="admin-login__form" onSubmit={handleSubmit} noValidate>
          <div className="admin-login__field">
            <label className="admin-login__label" htmlFor="admin-username">
              Username
            </label>
            <input
              id="admin-username"
              className="admin-login__input"
              type="text"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={submitting}
              placeholder="admin@jiit"
            />
          </div>

          <div className="admin-login__field">
            <label className="admin-login__label" htmlFor="admin-password">
              Password
            </label>
            <input
              id="admin-password"
              className="admin-login__input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={submitting}
              placeholder="••••••••"
            />
          </div>

          {error ? (
            <p className="admin-login__error" id="admin-login-error" role="alert">
              <Icon name="alert-circle" size={15} />
              {error}
            </p>
          ) : null}

          <Button type="submit" variant="primary" loading={submitting} className="admin-login__submit">
            Sign in
          </Button>
        </form>
      </section>
    </div>
  );
}
