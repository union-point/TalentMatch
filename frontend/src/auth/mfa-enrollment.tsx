import { useState } from 'react';
import type { FormEvent } from 'react';
import { useAuth } from '@/auth/auth-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchPost } from '@/lib/api';
import type { RecoverySession } from '@/types/auth';

export function RecoveryCodes({
  codes,
  onDone,
}: {
  codes: string[];
  onDone: () => void;
}) {
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-4">
      <p className="text-sm">
        Save these recovery codes somewhere secure. Each works once and this
        list will not be shown again. Losing your authenticator and all codes
        means losing account access.
      </p>
      <textarea
        aria-label="Recovery codes"
        className="h-52 w-full rounded-md border bg-muted p-3 font-mono text-xs"
        readOnly
        value={codes.join('\n')}
      />
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
        />
        I saved my recovery codes
      </label>
      <Button disabled={!saved} onClick={onDone}>
        Continue
      </Button>
    </div>
  );
}

export function MfaEnrollment({
  replacing,
  onComplete,
}: {
  replacing: boolean;
  onComplete: () => void;
}) {
  const { update } = useAuth();
  const [password, setPassword] = useState('');
  const [factor, setFactor] = useState('');
  const [code, setCode] = useState('');
  const [setup, setSetup] = useState<{ uri: string; qr_code: string } | null>(
    null
  );
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (!setup) {
        setSetup(
          await fetchPost('/v1/auth/mfa/enroll', {
            password,
            ...(replacing ? { code: factor.trim() } : {}),
          })
        );
        setPassword('');
        setFactor('');
      } else {
        const result = await fetchPost<RecoverySession>('/v1/auth/mfa/confirm', {
          code: code.trim(),
        });
        const { recovery_codes: codes, ...session } = result;
        update(session);
        setRecoveryCodes(codes);
        setSetup(null);
        setCode('');
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Enrollment failed.');
    } finally {
      setBusy(false);
    }
  }

  if (recoveryCodes)
    return <RecoveryCodes codes={recoveryCodes} onDone={onComplete} />;
  return (
    <form onSubmit={submit} className="space-y-4">
      {!setup ? (
        <>
          <label className="block space-y-1 text-sm">
            Current password
            <Input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              maxLength={128}
              required
            />
          </label>
          {replacing && (
            <label className="block space-y-1 text-sm">
              Current authenticator or recovery code
              <Input
                autoComplete="one-time-code"
                value={factor}
                onChange={(e) => setFactor(e.target.value)}
                maxLength={128}
                required
              />
            </label>
          )}
        </>
      ) : (
        <>
          <img
            src={setup.qr_code}
            alt="Scan this QR code with your authenticator app"
            width={240}
            height={240}
          />
          <details className="text-sm">
            <summary>Enter a setup key manually</summary>
            <p className="break-all font-mono text-xs">
              {new URL(setup.uri).searchParams.get('secret')}
            </p>
          </details>
          <p className="text-sm text-muted-foreground">
            Add TalentMatch in your authenticator, then enter its six-digit
            code. Setup expires after ten minutes.
          </p>
          <label className="block space-y-1 text-sm">
            Authentication code
            <Input
              autoComplete="one-time-code"
              inputMode="numeric"
              pattern="[0-9]{6}"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
            />
          </label>
        </>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={busy}>
        {busy
          ? 'Please wait…'
          : setup
            ? 'Confirm authenticator'
            : replacing
              ? 'Set up replacement'
              : 'Set up authenticator'}
      </Button>
    </form>
  );
}
