import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { useAuth } from '@/auth/auth-context';
import { AuthShell } from '@/auth/auth-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchPost } from '@/lib/api';
import { sessionDestination, safeReturnTo } from '@/lib/auth-navigation';
import type { AuthSession } from '@/types/auth';

type Mode =
  | 'login'
  | 'signup'
  | 'forgot-password'
  | 'verify-email'
  | 'reset-password'
  | 'accept-invitation';
const titles: Record<Mode, string> = {
  login: 'Sign in',
  signup: 'Create your organization',
  'forgot-password': 'Reset your password',
  'verify-email': 'Verify your email',
  'reset-password': 'Choose a new password',
  'accept-invitation': 'Join your team',
};

export function AuthForm({ mode }: { mode: Mode }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [token] = useState(
    () =>
      new URLSearchParams(location.hash.slice(1)).get('token') ??
      (mode === 'accept-invitation' ? auth.invitationToken : '')
  );
  const [email, setEmail] = useState(auth.session?.user?.email ?? '');
  const [password, setPassword] = useState('');
  const [organization, setOrganization] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const returnTo = safeReturnTo(params.get('returnTo'));
  const needsPassword =
    mode === 'login' ||
    mode === 'signup' ||
    mode === 'reset-password' ||
    (mode === 'accept-invitation' && auth.session?.state !== 'authenticated');
  const needsEmail =
    mode === 'login' ||
    mode === 'signup' ||
    mode === 'forgot-password' ||
    (mode === 'verify-email' && !token);

  useEffect(() => {
    if (location.hash)
      window.history.replaceState(
        null,
        '',
        location.pathname + location.search
      );
  }, [location.hash, location.pathname, location.search]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      if (mode === 'login') {
        const session = await fetchPost<AuthSession>('/v1/auth/login', {
          email,
          password,
        });
        auth.update(session);
        navigate(sessionDestination(session, returnTo), { replace: true });
      } else if (mode === 'signup') {
        const result = await fetchPost<{ detail: string }>(
          '/v1/auth/register',
          { email, password, organization_name: organization }
        );
        setMessage(result.detail);
      } else if (
        mode === 'forgot-password' ||
        (mode === 'verify-email' && !token)
      ) {
        const result = await fetchPost<{ detail: string }>(
          `/v1/auth/${mode === 'forgot-password' ? 'forgot-password' : 'resend-verification'}`,
          { email }
        );
        setMessage(result.detail);
      } else if (mode === 'accept-invitation') {
        const session = await fetchPost<AuthSession>(
          '/v1/auth/accept-invitation',
          { token, ...(password ? { password } : {}) }
        );
        auth.rememberInvitation('');
        auth.update(session);
        navigate(sessionDestination(session), { replace: true });
      } else {
        const result = await fetchPost<{ detail: string }>(`/v1/auth/${mode}`, {
          token,
          ...(mode === 'reset-password' ? { password } : {}),
        });
        await auth.refresh();
        setMessage(result.detail);
      }
      setPassword('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Please try again.');
    } finally {
      setBusy(false);
    }
  }

  const missingLink =
    ['reset-password', 'accept-invitation'].includes(mode) && !token;
  return (
    <AuthShell
      title={titles[mode]}
      description={
        mode === 'signup'
          ? 'Create a private workspace for your hiring team. Verify your email and set up an authenticator to get started.'
          : undefined
      }
    >
      {missingLink ? (
        <p role="alert">
          Open the complete link from your email. Links expire and can only be
          used once.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {needsEmail && (
            <label className="block space-y-1 text-sm">
              Email
              <Input
                type="email"
                name="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
          )}
          {mode === 'signup' && (
            <label className="block space-y-1 text-sm">
              Organization name
              <Input
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                maxLength={255}
                required
              />
            </label>
          )}
          {(needsPassword || mode === 'accept-invitation') && (
            <label className="block space-y-1 text-sm">
              {mode === 'login' ? 'Password' : 'New password'}
              {mode === 'accept-invitation' && !needsPassword
                ? ' (new accounts only)'
                : ''}
              <Input
                type="password"
                name="password"
                autoComplete={
                  mode === 'login' ? 'current-password' : 'new-password'
                }
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={mode === 'login' ? 1 : 15}
                maxLength={128}
                required={needsPassword}
              />
              {mode !== 'login' && (
                <span className="text-xs text-muted-foreground">
                  Use at least 15 characters. Spaces are welcome.
                </span>
              )}
            </label>
          )}
          {mode === 'accept-invitation' && (
            <p className="text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link
                className="underline"
                onClick={() => auth.rememberInvitation(token)}
                to="/login?returnTo=%2Faccept-invitation"
              >
                Sign in to the invited account
              </Link>
              . Each account can belong to one organization.
            </p>
          )}
          {mode === 'verify-email' && token && (
            <p className="text-sm">Confirm your email address to continue.</p>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="text-sm">
              {message}
            </p>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={busy || auth.loading}
          >
            {busy
              ? 'Please wait…'
              : mode === 'verify-email' && !token
                ? 'Resend verification email'
                : mode === 'accept-invitation'
                  ? 'Accept invitation'
                  : titles[mode]}
          </Button>
        </form>
      )}
      <div className="flex flex-wrap gap-4 text-sm">
        {mode !== 'login' && (
          <Link to="/login" className="underline">
            Sign in
          </Link>
        )}
        {mode === 'login' && (
          <>
            <Link to="/signup" className="underline">
              Create account
            </Link>
            <Link to="/forgot-password" className="underline">
              Forgot password?
            </Link>
            <Link to="/verify-email" className="underline">
              Verify email
            </Link>
          </>
        )}
      </div>
    </AuthShell>
  );
}
