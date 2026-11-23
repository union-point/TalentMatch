import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/auth/auth-context';
import { AuthShell } from '@/auth/auth-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchPost } from '@/lib/api';
import { safeReturnTo, sessionDestination } from '@/lib/auth-navigation';
import type { AuthSession } from '@/types/auth';

export function MfaPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const returnTo = safeReturnTo(params.get('returnTo'));
  async function challenge(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const session = await fetchPost<AuthSession>('/v1/auth/mfa/challenge', {
        code: code.trim(),
      });
      auth.update(session);
      navigate(sessionDestination(session, returnTo), { replace: true });
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not verify the code.'
      );
    } finally {
      setCode('');
      setBusy(false);
    }
  }
  if (auth.loading)
    return (
      <p className="p-8" role="status">
        Checking your session…
      </p>
    );
  if (auth.session?.state !== 'mfa_challenge_required')
    return (
      <Navigate
        to={sessionDestination(auth.session, returnTo)}
        replace
      />
    );
  return (
    <AuthShell
      title="Verify your sign-in"
      description="Enter a code from your authenticator app or one unused recovery code."
    >
      <form onSubmit={challenge} className="space-y-4">
        <label className="block space-y-1 text-sm">
          Authenticator or recovery code
          <Input
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={128}
            required
          />
        </label>
        <Button type="submit" disabled={busy}>
          {busy ? 'Checking…' : 'Verify'}
        </Button>
      </form>
      {error && (
        <p role="alert" className="text-sm">
          {error}
        </p>
      )}
      <Button
        variant="ghost"
        onClick={() => {
          void auth
            .logout()
            .then(() => navigate('/login'))
            .catch((cause) => setError(cause.message));
        }}
      >
        Sign out
      </Button>
    </AuthShell>
  );
}
