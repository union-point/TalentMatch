import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { ArrowRight, Mail } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { AuthPasswordField } from '@/auth/auth-password-field';
import { AuthShell } from '@/auth/auth-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ApiError, fetchPost } from '@/lib/api';
import {
  forgotPasswordPath,
  pendingVerificationPath,
  safeReturnTo,
  sessionDestination,
  verificationPath,
  verificationResendDelayMs,
  withReturnTo,
} from '@/lib/auth-navigation';
import type { AuthSession } from '@/types/auth';

type Mode = 'login' | 'signup' | 'accept-invitation';
const titles: Record<Mode, string> = {
  login: 'Sign in',
  signup: 'Create your organization',
  'accept-invitation': 'Join your team',
};

export function AuthForm({ mode, destination }: { mode: Mode; destination?: string }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const loginState = location.state as { email?: string } | null;
  const signedOut = params.get('signedOut');
  const signInDescription = signedOut === 'everywhere' ? 'You’ve signed out on all devices.'
    : signedOut === 'device' ? 'You’ve signed out on this device.'
      : 'Welcome back. Enter your details to access your workspace.';
  const fromPasswordReset = mode === 'login' && params.get('source') === 'password-reset';
  const [token] = useState(
    () =>
      new URLSearchParams(location.hash.slice(1)).get('token') ??
      (mode === 'accept-invitation' ? auth.invitationToken : '')
  );
  const [email, setEmail] = useState(
    () => loginState?.email ?? (fromPasswordReset ? '' : auth.session?.user?.email ?? '')
  );
  const [password, setPassword] = useState('');
  const [organization, setOrganization] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const registration = useMutation({
    gcTime: 0,
    mutationFn: (body: { email: string; password: string; organization_name: string }) =>
      fetchPost('/v1/auth/register', body),
    onError: (cause) => {
      if (cause instanceof ApiError && cause.code === 'csrf_failed') void auth.refresh();
    },
  });
  const formBusy = busy || registration.isPending;
  const formError = registration.error
    ? registration.error instanceof ApiError ? registration.error.message : 'Couldn’t create your organization. Try again.'
    : error;
  const returnTo = safeReturnTo(destination ?? params.get('returnTo'));
  const needsPassword =
    mode !== 'accept-invitation' || auth.session?.state !== 'authenticated';
  const needsEmail = mode !== 'accept-invitation';

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
    if (submitting.current || auth.loading) return;
    submitting.current = true;
    if (mode === 'signup') {
      const address = email.trim();
      registration.mutate({ email: address, password, organization_name: organization.trim() }, {
        onSuccess: () => navigate(withReturnTo(pendingVerificationPath, returnTo), {
          replace: true,
          state: { email: address, fromSignup: true, retryAt: Date.now() + verificationResendDelayMs },
        }),
        onSettled: () => { submitting.current = false; },
      });
      return;
    }
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') {
        const session = await fetchPost<AuthSession>('/v1/auth/login', {
          email,
          password,
        });
        auth.update(session);
        navigate(sessionDestination(session, returnTo), {
          replace: true,
          state: session.state === 'email_verification_required' ? { email: session.user?.email } : undefined,
        });
      } else {
        const session = await fetchPost<AuthSession>(
          '/v1/auth/accept-invitation',
          { token, ...(password ? { password } : {}) }
        );
        auth.rememberInvitation('');
        auth.update(session);
        navigate(sessionDestination(session), { replace: true });
      }
      setPassword('');
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'csrf_failed') void auth.refresh();
      setError(cause instanceof Error ? cause.message : 'Please try again.');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  if (
    !auth.error &&
    (mode === 'signup' || (mode === 'login' && !destination && !fromPasswordReset)) &&
    (auth.session?.state === 'authenticated' || auth.session?.state === 'mfa_challenge_required' ||
      (mode === 'signup' && auth.session?.state === 'email_verification_required'))
  ) {
    return <Navigate replace to={sessionDestination(auth.session, returnTo)} />;
  }

  const missingLink = mode === 'accept-invitation' && !token;
  return (
    <AuthShell
      focusTitle={mode === 'signup' || mode === 'login'}
      returnTo={returnTo}
      accountLink={mode === 'signup' ? 'login' : mode === 'login' ? 'signup' : undefined}
      title={titles[mode]}
      description={{
        login: signInDescription,
        signup: 'Create a private workspace for your hiring team.',
        'accept-invitation': 'Accept your invitation to the hiring workspace.',
      }[mode]}
    >
      {missingLink ? (
        <p role="alert">
          Open the complete link from your email. Links expire and can only be
          used once.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5" aria-busy={formBusy}>
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
                name="organization"
                autoComplete="organization"
                pattern={String.raw`.*\S.*`}
                maxLength={255}
                required
              />
            </label>
          )}
          <AuthPasswordField
            current={mode === 'login'}
            required={needsPassword}
            value={password}
            onChange={setPassword}
            action={mode === 'login' && (
              <Link to={withReturnTo(forgotPasswordPath, returnTo)} className="text-link text-xs">
                Forgot password?
              </Link>
            )}
          />
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
          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={formBusy || auth.loading}
          >
            {formBusy
              ? mode === 'signup' ? 'Creating organization…' : 'Please wait…'
              : mode === 'accept-invitation' ? 'Accept invitation' : titles[mode]}
            <ArrowRight size={16} />
          </Button>
        </form>
      )}
      {mode === 'login' ? (
        <div className="flex items-center gap-2 border-t pt-5 text-xs text-muted-foreground">
          <Mail size={15} aria-hidden /> Need a verification link?
          <Link to={withReturnTo(verificationPath, returnTo)} className="text-link text-foreground">Request a link</Link>
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
