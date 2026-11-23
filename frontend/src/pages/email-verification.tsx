import { useRef } from 'react';
import type { FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { AuthShell } from '@/auth/auth-shell';
import { Button, buttonVariants } from '@/components/ui/button';
import { useCooldown, useVerificationRetry } from '@/auth/verification-cooldown';
import { VerificationEmailForm } from '@/auth/verification-email-form';
import type { PendingEmail } from '@/auth/verification-email-form';
import { ApiError, fetchPost } from '@/lib/api';
import {
  pendingVerificationPath,
  safeReturnTo,
  sessionDestination,
  verificationPath,
  withReturnTo,
} from '@/lib/auth-navigation';
import { cn } from '@/lib/utils';

type Outcome = 'verified' | 'expired' | 'invalid' | 'used';

const primaryLink = cn(buttonVariants(), 'min-h-[46px] w-full');
const secondaryLink = 'text-link w-fit text-sm';

function useReturnTo(): string {
  const [params] = useSearchParams();
  return safeReturnTo(params.get('returnTo'));
}

export function EmailVerification() {
  const { hash, state } = useLocation();
  const { session, loading } = useAuth();
  const returnTo = useReturnTo();
  const token = new URLSearchParams(hash.slice(1)).get('token');
  const outcome = (state as { outcome?: Outcome } | null)?.outcome;

  if (token !== null) return <VerifyLink key={token} token={token} returnTo={returnTo} />;
  if (outcome) return <VerificationResult outcome={outcome} returnTo={returnTo} />;
  if (loading) return <VerificationLoading />;
  if (session?.state === 'email_verification_required' && session.user)
    return <Navigate replace to={withReturnTo(pendingVerificationPath, returnTo)} state={{ email: session.user.email }} />;

  return <VerificationEmailForm returnTo={returnTo} />;
}

export function PendingVerification() {
  const { state } = useLocation();
  const { session, loading, error } = useAuth();
  const returnTo = useReturnTo();
  const pending = typeof state?.email === 'string' ? state as PendingEmail : null;
  const pendingUser = session?.state === 'email_verification_required' ? session.user : null;
  const email = pendingUser && pendingUser.email !== pending?.email ? { email: pendingUser.email } : pending;

  if (loading && !email) return <VerificationLoading />;
  if (!error && (!pending || pending.email.toLowerCase() === session?.user?.email.toLowerCase()) &&
    (session?.state === 'authenticated' || session?.state === 'mfa_challenge_required'))
    return <Navigate replace to={sessionDestination(session, returnTo)} />;
  if (!email) return <Navigate replace to={withReturnTo(verificationPath, returnTo)} />;

  return <VerificationEmailForm key={email.email} pending={email} returnTo={returnTo} requiresVerification={Boolean(pendingUser)} />;
}

function VerificationLoading() {
  return (
    <AuthShell title="Email verification">
      <p role="status" className="text-sm text-muted-foreground">Checking your session…</p>
    </AuthShell>
  );
}

function VerifyLink({ token, returnTo }: { token: string; returnTo: string }) {
  const { loading, refresh, session } = useAuth();
  const submitting = useRef(false);
  const { rateLimitedUntil, rememberRateLimit } = useVerificationRetry();
  const seconds = useCooldown(rateLimitedUntil);
  const verification = useMutation({
    gcTime: 0,
    mutationFn: () => fetchPost('/v1/auth/verify-email', { token }),
    onSuccess: () => {
      if (session?.state === 'email_verification_required') void refresh();
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return;
      if (error.code === 'csrf_failed') void refresh();
    },
  });
  const error = verification.error;
  let outcome: Outcome | undefined;
  if (verification.isSuccess) outcome = 'verified';
  else if (token.length < 20 || token.length > 128) outcome = 'invalid';
  else if (error instanceof ApiError) {
    if (error.code === 'expired_token') outcome = 'expired';
    if (error.code === 'used_token') outcome = 'used';
    if (error.code === 'invalid_token' || error.status === 422) outcome = 'invalid';
  }

  if (outcome)
    return <Navigate replace to={withReturnTo(verificationPath, returnTo)} state={{ outcome }} />;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading || submitting.current || Date.now() < rateLimitedUntil) return;
    submitting.current = true;
    verification.mutate(undefined, {
      onError: (cause) => {
        if (cause instanceof ApiError && cause.status === 429) rememberRateLimit(cause);
      },
      onSettled: () => { submitting.current = false; },
    });
  }

  const feedback = error instanceof ApiError ? error.message
    : error ? 'Couldn’t verify your email. Try again.'
      : seconds > 0 ? 'Too many attempts. Try again when the timer ends.' : '';

  return (
    <AuthShell
      focusTitle
      title="Verify your email"
      description="Confirm this email address to finish setting up your TalentMatch account."
    >
      <form onSubmit={submit} className="space-y-4" aria-busy={verification.isPending}>
        {feedback && (
          <p role="alert" className="text-sm text-destructive">
            {feedback}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={loading || verification.isPending || seconds > 0}>
          {verification.isPending ? 'Verifying…' : loading ? 'Checking your session…'
            : seconds > 0 ? `Try again in ${seconds}s` : error ? 'Try again' : 'Verify email'}
          <ArrowRight size={16} aria-hidden />
        </Button>
      </form>
    </AuthShell>
  );
}

function VerificationResult({ outcome, returnTo }: { outcome: Outcome; returnTo: string }) {
  const { session, loading, error } = useAuth();
  const titles: Record<Outcome, string> = {
    verified: 'Email verified',
    expired: 'This link has expired',
    invalid: 'This link is invalid',
    used: 'This link is no longer active',
  };
  const signIn = withReturnTo('/login', returnTo);
  const canContinue = !error && (
    session?.state === 'authenticated' || session?.state === 'mfa_challenge_required'
  );
  const next = canContinue ? sessionDestination(session, returnTo) : signIn;
  const nextPath = next.split(/[?#]/)[0];
  const action = canContinue
    ? session?.state === 'mfa_challenge_required' ? 'Continue signing in'
      : nextPath === '/account' ? 'Open account'
        : nextPath === '/accept-invitation' ? 'Open invitation' : 'Open workspace'
    : 'Sign in';
  const needsLink = outcome === 'invalid' || outcome === 'expired';
  const newLink = withReturnTo(verificationPath, returnTo);

  return (
    <AuthShell
      focusTitle
      title={titles[outcome]}
      description={loading ? undefined : outcome === 'verified'
        ? canContinue ? 'You can continue to TalentMatch.' : 'Sign in to open your workspace.'
        : outcome === 'used'
          ? canContinue ? 'Continue to TalentMatch or request a new link.'
            : 'If you’ve already verified your email, sign in. Otherwise, request a new link.'
          : 'Request a new verification link to confirm your email.'}
    >
      {loading ? (
        <p role="status" className="text-sm text-muted-foreground">Checking your session…</p>
      ) : (
        <>
          <Link className={primaryLink} to={needsLink ? newLink : next}>
            {needsLink ? 'Request a new link' : action}
            <ArrowRight size={16} aria-hidden />
          </Link>
          {outcome !== 'verified' && (
            <Link className={secondaryLink} to={needsLink ? next : newLink}>
              {needsLink ? action : 'Request a new link'}
            </Link>
          )}
        </>
      )}
    </AuthShell>
  );
}
