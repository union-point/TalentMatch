import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, Mail } from 'lucide-react';
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

export function AuthForm({ mode, destination }: { mode: Mode; destination?: string }) {
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
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const returnTo = safeReturnTo(destination ?? params.get('returnTo'));
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
      accountLink={mode === 'signup' ? 'login' : mode === 'login' ? 'signup' : undefined}
      title={titles[mode]}
      description={{
        login: 'Welcome back. Enter your details to access your workspace.',
        signup: 'Create a private workspace for your hiring team.',
        'forgot-password': 'Enter your email to request a password reset link.',
        'verify-email': token ? undefined : 'Request a new verification link for your account.',
        'reset-password': 'Set a new password for your TalentMatch account.',
        'accept-invitation': 'Accept your invitation to the hiring workspace.',
      }[mode]}
    >
      {missingLink ? (
        <p role="alert">
          Open the complete link from your email. Links expire and can only be
          used once.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {needsEmail && (
            <label className="block space-y-1 text-sm">
              Email
              <Input
                type="email"
                placeholder="you@company.com"
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
            <div className="space-y-1">
              <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
                <label htmlFor="auth-password">
                  {mode === 'login' ? 'Password' : 'New password'}
                  {mode === 'accept-invitation' && !needsPassword && ' (new accounts only)'}
                </label>
                {mode === 'login' && <Link to="/forgot-password" className="text-link text-xs">Forgot password?</Link>}
              </div>
              <div className="relative">
                <Input id="auth-password" type={showPassword ? 'text' : 'password'}
                  name="password" className="pr-12"
                  placeholder={mode === 'login' ? 'Enter your password' : 'Choose a password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  minLength={mode === 'login' ? 1 : 15} maxLength={128} required={needsPassword}
                />
                <button type="button" className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {mode !== 'login' && <p className="text-xs text-muted-foreground">Use at least 15 characters. Spaces are welcome.</p>}
            </div>
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
            <ArrowRight size={16} />
          </Button>
        </form>
      )}
      {mode === 'login' ? (
        <div className="flex items-center gap-2 border-t pt-5 text-xs text-muted-foreground">
          <Mail size={15} /> Need to confirm your email?
          <Link to="/verify-email" className="text-link text-foreground">Verify email</Link>
        </div>
      ) : mode !== 'signup' && (
        <Link to="/login" className="text-link w-fit text-sm">Sign in</Link>
      )}
      {destination && auth.error && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          Couldn’t connect to your workspace.
          <button className="text-link" onClick={() => void auth.refresh()}>Retry</button>
        </div>
      )}
    </AuthShell>
  );
}
