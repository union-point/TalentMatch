import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Mail } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { useAuthRequestRetry, useCooldown } from '@/auth/auth-request-cooldown';
import { AuthShell } from '@/auth/auth-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ApiError, fetchPost } from '@/lib/api';
import {
  forgotPasswordPath,
  passwordResetInboxPath,
  safeReturnTo,
  withReturnTo,
} from '@/lib/auth-navigation';

interface RequestedReset {
  email: string;
  resendAt: number;
  resent?: boolean;
}

const resendDelayMs = 60_000;
const textLink = 'text-link w-fit text-sm';

export function PasswordResetRequest({ inbox = false }: { inbox?: boolean }) {
  const { state } = useLocation();
  const [params] = useSearchParams();
  const returnTo = safeReturnTo(params.get('returnTo'));

  if (!inbox) return <ResetEmailForm key="request" returnTo={returnTo} />;
  if (typeof state?.email !== 'string')
    return <Navigate to={withReturnTo(forgotPasswordPath, returnTo)} replace />;

  return <ResetEmailForm key="inbox" requested={state as RequestedReset} returnTo={returnTo} />;
}

function ResetEmailForm({ requested, returnTo }: { requested?: RequestedReset; returnTo: string }) {
  const { loading, refresh } = useAuth();
  const navigate = useNavigate();
  const { address, rateLimitedUntil, rememberRateLimit } = useAuthRequestRetry();
  const [email, setEmail] = useState(address);
  const submitting = useRef(false);
  const retryAt = Math.max(requested?.resendAt ?? 0, rateLimitedUntil);
  const seconds = useCooldown(retryAt);
  const throttled = seconds > 0 && rateLimitedUntil >= retryAt;
  const send = useMutation({
    mutationFn: (email: string) => fetchPost('/v1/auth/forgot-password', { email }),
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'csrf_failed') void refresh();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading || submitting.current || Date.now() < retryAt) return;
    submitting.current = true;
    const address = requested?.email ?? email.trim();
    send.mutate(address, {
      onSuccess: () => navigate(withReturnTo(passwordResetInboxPath, returnTo), {
        replace: true,
        state: { email: address, resendAt: Date.now() + resendDelayMs, resent: Boolean(requested) },
      }),
      onError: (error) => {
        if (error instanceof ApiError && error.status === 429) rememberRateLimit(error, address);
      },
      onSettled: () => { submitting.current = false; },
    });
  }

  let feedback = '';
  if (throttled) feedback = 'Too many requests. Try again when the timer ends.';
  else if (send.error && !(send.error instanceof ApiError && send.error.status === 429)) {
    feedback = send.error instanceof ApiError ? send.error.message : 'Couldn’t request a reset link. Try again.';
  }
  const readyLabel = requested ? 'Send another link' : 'Send reset link';
  const submitLabel = send.isPending ? 'Requesting link…'
    : loading ? 'Checking your session…'
      : seconds > 0 ? `${throttled ? 'Try again' : 'Resend'} in ${seconds}s` : readyLabel;

  return (
    <AuthShell
      focusTitle
      title={requested ? 'Check your email' : 'Reset your password'}
      description={requested
        ? 'If a reset link is available for this address, we’ll send it by email. Check spam or junk while you wait.'
        : 'Enter the email address you use for TalentMatch.'}
    >
      {requested && (
        <div className="flex min-w-0 items-center gap-3 rounded-md border bg-card p-4">
          <Mail size={18} className="shrink-0 text-muted-foreground" aria-hidden />
          <p className="min-w-0 text-sm [overflow-wrap:anywhere]">{requested.email}</p>
        </div>
      )}
      <form onSubmit={submit} className="space-y-4" aria-busy={send.isPending}>
        {!requested && (
          <label className="block space-y-1 text-sm">
            Email
            <Input
              type="email"
              name="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              readOnly={send.isPending}
              required
            />
          </label>
        )}
        {requested && (
          <p className="text-sm text-muted-foreground">Use the most recent reset link you receive.</p>
        )}
        {feedback && <p role="alert" className="text-sm text-destructive">{feedback}</p>}
        {requested?.resent && !feedback && !send.isPending && (
          <p role="status" className="text-sm text-muted-foreground">New link requested.</p>
        )}
        <Button
          type="submit"
          className="w-full"
          variant={requested ? 'outline' : 'default'}
          disabled={loading || send.isPending || seconds > 0}
        >
          {submitLabel}
          <ArrowRight size={16} aria-hidden />
        </Button>
      </form>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-t pt-4">
        <Link to={withReturnTo('/login', returnTo)} className={textLink}>Back to sign in</Link>
        {requested && (
          <Link to={withReturnTo(forgotPasswordPath, returnTo)} className={textLink}>
            Use a different email
          </Link>
        )}
      </div>
    </AuthShell>
  );
}
