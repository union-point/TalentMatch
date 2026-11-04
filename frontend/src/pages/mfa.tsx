import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/auth/auth-context';
import { AuthShell } from '@/auth/auth-shell';
import { MfaEnrollment } from '@/auth/mfa-enrollment';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchPost } from '@/lib/api';
import { safeReturnTo } from '@/lib/auth-navigation';
import type { AuthSession } from '@/types/auth';

export function MfaPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [enrollmentActive, setEnrollmentActive] = useState(false);
  useEffect(() => {
    if (auth.session?.state === 'mfa_enrollment_required')
      setEnrollmentActive(true);
  }, [auth.session?.state]);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const returnTo = safeReturnTo(params.get('returnTo'));
  function complete(session: AuthSession) {
    auth.update(session);
    navigate(returnTo, { replace: true });
  }
  async function challenge(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      complete(
        await fetchPost<AuthSession>('/v1/auth/mfa/challenge', {
          code: code.trim(),
        })
      );
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
  if (auth.session?.state === 'authenticated' && !enrollmentActive)
    return (
      <Navigate
        to={auth.session.organization ? returnTo : '/account'}
        replace
      />
    );
  if (!auth.session?.user) return <Navigate to="/login" replace />;
  if (auth.session.state === 'email_verification_required')
    return <Navigate to="/verify-email" replace />;
  return (
    <AuthShell
      title={
        auth.session.state === 'mfa_enrollment_required'
          ? 'Protect your owner account'
          : 'Verify your sign-in'
      }
      description={
        auth.session.state === 'mfa_enrollment_required'
          ? 'Organization owners must set up an authenticator before accessing hiring data.'
          : 'Enter a code from your authenticator app or one unused recovery code.'
      }
    >
      {auth.session.state === 'mfa_enrollment_required' || enrollmentActive ? (
        <MfaEnrollment replacing={false} onComplete={complete} />
      ) : (
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
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? 'Checking…' : 'Verify'}
          </Button>
        </form>
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
