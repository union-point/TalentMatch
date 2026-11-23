import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { AuthPasswordField } from '@/auth/auth-password-field';
import { useAuthRequestRetry, useCooldown } from '@/auth/auth-request-cooldown';
import { AuthShell } from '@/auth/auth-shell';
import { Button, buttonVariants } from '@/components/ui/button';
import { ApiError, fetchPost, resetSessionToken } from '@/lib/api';
import { forgotPasswordPath, resetPasswordPath, safeReturnTo, withReturnTo } from '@/lib/auth-navigation';
import { cn } from '@/lib/utils';

type Outcome = 'complete' | 'unavailable';
const primaryLink = cn(buttonVariants(), 'min-h-[46px] w-full');

export function ResetPassword() {
  const { hash, state } = useLocation();
  const [params] = useSearchParams();
  const returnTo = safeReturnTo(params.get('returnTo'));
  const token = new URLSearchParams(hash.slice(1)).get('token');
  const outcome = (state as { outcome?: Outcome } | null)?.outcome;

  if (params.has('token'))
    return <Navigate replace to={withReturnTo(resetPasswordPath, returnTo) + hash} />;
  if (token === null && !hash)
    return <ResetResult outcome={outcome === 'complete' ? 'complete' : 'unavailable'} returnTo={returnTo} />;
  if (!token || token.length < 20 || token.length > 128)
    return <Navigate replace to={withReturnTo(resetPasswordPath, returnTo)} state={{ outcome: 'unavailable' }} />;

  return <ResetForm key={token} token={token} returnTo={returnTo} />;
}

function ResetForm({ token, returnTo }: { token: string; returnTo: string }) {
  const { loading, refresh, update } = useAuth();
  const navigate = useNavigate();
  const { rateLimitedUntil, rememberRateLimit } = useAuthRequestRetry();
  const seconds = useCooldown(rateLimitedUntil);
  const [password, setPassword] = useState('');
  const submitting = useRef(false);
  const reset = useMutation({
    gcTime: 0,
    mutationFn: (password: string) => fetchPost('/v1/auth/reset-password', { token, password }),
    onSuccess: () => {
      resetSessionToken();
      update(null);
      void refresh();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'csrf_failed') void refresh();
    },
  });

  function showResult(outcome: Outcome) {
    setPassword('');
    navigate(withReturnTo(resetPasswordPath, returnTo), { replace: true, state: { outcome } });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading || submitting.current || Date.now() < rateLimitedUntil) return;
    submitting.current = true;
    reset.mutate(password, {
      onSuccess: () => showResult('complete'),
      onError: (error) => {
        if (!(error instanceof ApiError)) return;
        if (error.code === 'invalid_token') showResult('unavailable');
        else if (error.status === 429) rememberRateLimit(error);
      },
      onSettled: () => { submitting.current = false; },
    });
  }

  let feedback = '';
  if (seconds > 0) feedback = 'Too many attempts. Try again when the timer ends.';
  else if (reset.error && !(reset.error instanceof ApiError && reset.error.status === 429)) {
    feedback = reset.error instanceof ApiError ? reset.error.message : 'Couldn’t update your password. Try again.';
  }
  const submitLabel = reset.isPending ? 'Updating password…'
    : loading ? 'Checking your session…'
      : seconds > 0 ? `Try again in ${seconds}s` : 'Update password';

  return (
    <AuthShell
      focusTitle
      title="Choose a new password"
      description="Changing your password signs you out on all devices."
    >
      <form onSubmit={submit} className="space-y-4" aria-busy={reset.isPending}>
        <AuthPasswordField value={password} onChange={setPassword} readOnly={reset.isPending} />
        {feedback && <p role="alert" className="text-sm text-destructive">{feedback}</p>}
        <Button type="submit" className="w-full" disabled={loading || reset.isPending || seconds > 0}>
          {submitLabel}
          <ArrowRight size={16} aria-hidden />
        </Button>
      </form>
    </AuthShell>
  );
}

function ResetResult({ outcome, returnTo }: { outcome: Outcome; returnTo: string }) {
  const complete = outcome === 'complete';
  const signIn = withReturnTo('/login', returnTo);
  const freshSignIn = signIn + (returnTo === '/' ? '?' : '&') + 'source=password-reset';

  return (
    <AuthShell
      focusTitle
      title={complete ? 'Password updated' : 'Reset link unavailable'}
      description={complete
        ? 'Sign in with your new password.'
        : 'Reset links expire and can only be used once.'}
    >
      {complete ? (
        <Link to={freshSignIn} className={primaryLink}>
          Sign in <ArrowRight size={16} aria-hidden />
        </Link>
      ) : (
        <>
          <Link to={withReturnTo(forgotPasswordPath, returnTo)} className={primaryLink}>
            Request a new link <ArrowRight size={16} aria-hidden />
          </Link>
          <Link to={signIn} className="text-link w-fit text-sm">Back to sign in</Link>
        </>
      )}
    </AuthShell>
  );
}
