import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/auth-context';
import { MfaEnrollment, RecoveryCodes } from '@/auth/mfa-enrollment';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchPost } from '@/lib/api';
import type { AuthSession, RecoverySession } from '@/types/auth';

export function Account() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [code, setCode] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [enroll, setEnroll] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      auth.update(
        await fetchPost<AuthSession>('/v1/auth/change-password', {
          password,
          new_password: newPassword,
        })
      );
      setMessage('Password changed. Other sessions have been signed out.');
      setPassword('');
      setNewPassword('');
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not change password.'
      );
    } finally {
      setBusy(false);
    }
  }
  async function manageMfa(disable: boolean) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await fetchPost<RecoverySession>(
        `/v1/auth/mfa/${disable ? 'disable' : 'recovery-codes'}`,
        { password, code: code.trim() }
      );
      auth.update(result);
      setCodes(result.recovery_codes ?? []);
      setMessage(
        disable
          ? 'Authenticator disabled. Other sessions have been signed out.'
          : 'New recovery codes created. Previous codes no longer work.'
      );
      setPassword('');
      setCode('');
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not update MFA.'
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-8">
      <div>
        <Link className="text-sm underline" to="/">
          TalentMatch
        </Link>
        <h1 className="mt-4 text-2xl font-semibold">Account security</h1>
        <p className="text-sm text-muted-foreground">
          {auth.session?.user?.email}
        </p>
      </div>
      {!auth.session?.organization && (
        <p role="status">
          You do not currently belong to an organization. Open a new team
          invitation from your email to join one.
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <section className="space-y-4 rounded-xl border p-6">
        <h2 className="font-semibold">Password</h2>
        <form onSubmit={changePassword} className="space-y-4">
          <label className="block space-y-1 text-sm">
            Current password
            <Input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              maxLength={128}
            />
          </label>
          <label className="block space-y-1 text-sm">
            New password
            <Input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={15}
              maxLength={128}
              required
            />
          </label>
          <Button type="submit" disabled={busy}>
            Change password
          </Button>
        </form>
      </section>
      <section className="space-y-4 rounded-xl border p-6">
        <h2 className="font-semibold">Authenticator app</h2>
        <p className="text-sm">
          {auth.session?.mfa_enabled ? 'Enabled' : 'Not enabled'}
          {auth.session?.organization?.role === 'owner'
            ? ' · Required for organization owners'
            : ''}
        </p>
        {enroll ? (
          <MfaEnrollment
            replacing={!!auth.session?.mfa_enabled}
            onComplete={(session) => {
              auth.update(session);
              setEnroll(false);
              setMessage(
                'Authenticator saved. Other sessions have been signed out.'
              );
            }}
          />
        ) : (
          <Button variant="outline" onClick={() => setEnroll(true)}>
            {auth.session?.mfa_enabled
              ? 'Replace authenticator'
              : 'Enable authenticator'}
          </Button>
        )}
        {!!codes.length && (
          <RecoveryCodes codes={codes} onDone={() => setCodes([])} />
        )}
        {auth.session?.mfa_enabled && !enroll && !codes.length && (
          <div className="space-y-3 border-t pt-4">
            <p className="text-sm">
              To regenerate recovery codes
              {auth.session.organization?.role !== 'owner'
                ? ' or disable MFA'
                : ''}
              , confirm your password and a current authenticator or recovery
              code.
            </p>
            <label className="block space-y-1 text-sm">
              Current password
              <Input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                maxLength={128}
              />
            </label>
            <label className="block space-y-1 text-sm">
              Authenticator or recovery code
              <Input
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={128}
              />
            </label>
            <div className="flex gap-2">
              <Button
                disabled={busy || !password || !code}
                onClick={() => void manageMfa(false)}
              >
                Regenerate recovery codes
              </Button>
              {auth.session.organization?.role !== 'owner' && (
                <Button
                  variant="destructive"
                  disabled={busy || !password || !code}
                  onClick={() => void manageMfa(true)}
                >
                  Disable MFA
                </Button>
              )}
            </div>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Save your recovery codes securely. If you lose both your authenticator
          and all recovery codes, access cannot be restored.
        </p>
      </section>
      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={() => {
            void auth
              .logout()
              .then(() => navigate('/login'))
              .catch((cause) => setError(cause.message));
          }}
        >
          Sign out
        </Button>
        <Button
          variant="destructive"
          onClick={() => {
            void auth
              .logout(true)
              .then(() => navigate('/login'))
              .catch((cause) => setError(cause.message));
          }}
        >
          Sign out everywhere
        </Button>
      </div>
    </div>
  );
}
