import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Mail } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { AuthShell } from '@/auth/auth-shell';
import { useAuthRequestRetry, useCooldown } from '@/auth/auth-request-cooldown';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ApiError, fetchPost } from '@/lib/api';
import {
  pendingVerificationPath,
  verificationPath,
  verificationResendDelayMs,
  withReturnTo,
} from '@/lib/auth-navigation';

export type PendingEmail = { email: string; fromSignup?: boolean; retryAt?: number; resent?: boolean };

const secondaryLink = 'text-link w-fit text-sm';

export function VerificationEmailForm({ pending, returnTo, requiresVerification = false }: {
  pending?: PendingEmail;
  returnTo: string;
  requiresVerification?: boolean;
}) {
  const { loading, refresh, logout } = useAuth();
  const navigate = useNavigate();
  const { rateLimitedUntil, address, rememberRateLimit } = useAuthRequestRetry();
  const [email, setEmail] = useState(pending?.email ?? address);
  const submitting = useRef(false);
  const retryAt = Math.max(pending?.retryAt ?? 0, rateLimitedUntil);
  const seconds = useCooldown(retryAt);
  const throttled = rateLimitedUntil > Date.now();
  const signIn = withReturnTo('/login', returnTo);
  const signOut = useMutation({ mutationFn: () => logout() });
  const resend = useMutation({
    mutationFn: (address: string) =>
      fetchPost('/v1/auth/resend-verification', { email: address }),
    onError: (error) => {
      if (!(error instanceof ApiError)) return;
      if (error.code === 'csrf_failed') void refresh();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading || signOut.isPending || submitting.current || Date.now() < retryAt) return;
    submitting.current = true;
    const submittedEmail = (pending?.email ?? email).trim();
    resend.mutate(submittedEmail, {
      onSuccess: () => navigate(withReturnTo(pendingVerificationPath, returnTo), {
        replace: true,
        state: {
          ...pending,
          email: submittedEmail,
          retryAt: Date.now() + verificationResendDelayMs,
          resent: true,
        },
      }),
      onError: (error) => {
        if (error instanceof ApiError && error.status === 429) rememberRateLimit(error, submittedEmail);
      },
      onSettled: () => { submitting.current = false; },
    });
  }

  const feedback = resend.error instanceof ApiError ? resend.error.message
    : resend.error ? 'Couldn’t send the request. Try again.'
      : throttled ? 'Too many attempts. Try again when the timer ends.' : '';
  const buttonLabel = pending ? 'Resend verification email' : 'Send verification link';
  return (
    <AuthShell
      focusTitle
      title={pending ? 'Check your email' : 'Request a verification link'}
      description={pending
        ? 'If you receive a verification email from TalentMatch, open the link to finish setup. Check spam or junk while you wait.'
        : 'Enter your email address. If it still needs verification, we’ll send you a link.'}
    >
      {pending && (
        <div className="flex min-w-0 items-center gap-3 rounded-md border bg-card p-4">
          <Mail size={18} className="shrink-0 text-muted-foreground" aria-hidden />
          <p className="min-w-0 text-sm [overflow-wrap:anywhere]">{pending.email}</p>
        </div>
      )}
      <form onSubmit={submit} className="space-y-4" aria-busy={resend.isPending}>
        {!pending && (
          <label className="block space-y-1 text-sm">
            Email
            <Input type="email" name="email" autoComplete="email" placeholder="you@company.com"
              value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
        )}
        {feedback && (
          <p role="alert" className="text-sm text-destructive">
            {feedback}
          </p>
        )}
        {pending?.resent && !feedback && (
          <p role="status" className="text-sm text-muted-foreground">
            New link requested.
          </p>
        )}
        <Button type="submit" variant={pending ? 'outline' : 'default'} className="w-full"
          disabled={loading || resend.isPending || signOut.isPending || seconds > 0}>
          {resend.isPending ? 'Sending request…' : seconds > 0
            ? `${throttled ? 'Try again' : 'Resend'} in ${seconds}s` : buttonLabel}
          <ArrowRight size={16} aria-hidden />
        </Button>
      </form>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-t pt-4">
        {requiresVerification ? (
          <Button
            type="button"
            variant="ghost"
            className="w-fit px-0"
            disabled={resend.isPending || signOut.isPending}
            onClick={() => signOut.mutate(undefined, {
              onSuccess: () => navigate(signIn, { replace: true }),
            })}
          >
            {signOut.isPending ? 'Signing out…' : 'Sign out'}
          </Button>
        ) : (
          <Link className={secondaryLink} to={signIn} state={pending ? { email: pending.email } : undefined}>
            Sign in
          </Link>
        )}
        {pending && !requiresVerification && (
          <Link className={secondaryLink}
            to={withReturnTo(pending.fromSignup ? '/signup' : verificationPath, returnTo)}>
            Use a different email
          </Link>
        )}
      </div>
      {signOut.error && (
        <p role="alert" className="text-sm text-destructive">{signOut.error.message}</p>
      )}
    </AuthShell>
  );
}
