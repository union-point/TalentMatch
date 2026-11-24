import { useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { useAuth } from '@/auth/auth-context';
import { AccountSecurityDialog } from '@/auth/account-security-dialog';
import type { AccountSecurityAction } from '@/auth/account-security-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { AuthSession } from '@/types/auth';

export function Account() {
  const { session, error, refresh } = useAuth();
  if (!session?.user) return null;
  return <AccountSettings key={session.user.id} session={session} error={error} refresh={refresh} />;
}

function AccountSettings({ session, error, refresh }: {
  session: AuthSession;
  error: string | null;
  refresh: () => Promise<void>;
}) {
  const [action, setAction] = useState<AccountSecurityAction | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const mfaEnabled = session.mfa_enabled;

  function open(event: MouseEvent<HTMLButtonElement>, next: AccountSecurityAction) {
    trigger.current = event.currentTarget;
    setAction(next);
  }

  return (
    <div className="max-w-4xl">
      <div className="page-heading">
        <h1 className="display-title">Account security</h1>
        <p>{session.user?.email}</p>
      </div>

      {error && !action && (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-4 text-sm">
          <p role="alert">Couldn’t refresh your session.</p>
          <Button variant="outline" onClick={() => void refresh()}>Retry</Button>
        </div>
      )}

      {!session.organization && (
        <p className="mt-5 rounded-lg border bg-card p-4 text-sm text-muted-foreground">
          You can manage your account here. Open a team invitation from your email to join an organization.
        </p>
      )}

      <div className="divide-y border-b">
        <section aria-labelledby="security-password" className="account-security-row py-7">
          <div className="min-w-0">
            <h2 id="security-password" className="settings-heading">Password</h2>
            <p className="mt-2 text-sm text-muted-foreground">Changing your password signs out your other sessions.</p>
          </div>
          <Button variant="outline" onClick={(event) => open(event, 'password')}>Change password</Button>
        </section>

        <section aria-labelledby="security-mfa" className="account-security-row py-7">
          <div className="min-w-0">
            <h2 id="security-mfa" className="settings-heading">Two-factor authentication</h2>
            <Badge variant={mfaEnabled ? 'default' : 'secondary'} className="mt-2">{mfaEnabled ? 'On' : 'Off'}</Badge>
            <p className="mt-2 text-sm text-muted-foreground">
              {mfaEnabled
                ? 'Sign-in requires a code from your authenticator app or a recovery code.'
                : 'Add a second step to sign in with an authenticator app.'}
            </p>
          </div>
          <Button variant="outline" className="h-auto min-h-10 max-w-full whitespace-normal py-2"
            onClick={(event) => open(event, mfaEnabled ? 'manage' : 'enable')}>
            {mfaEnabled ? 'Manage two-factor authentication' : 'Enable authenticator'}
          </Button>
        </section>

        <section aria-labelledby="security-sessions" className="py-7">
          <h2 id="security-sessions" className="settings-heading">Sessions</h2>
          <div className="mt-2 divide-y">
            <div className="account-security-row py-4">
              <h3 className="text-sm font-medium">This device</h3>
              <Button variant="outline" onClick={(event) => open(event, 'sign-out')}>Sign out</Button>
            </div>
            <div className="account-security-row pt-4">
              <h3 className="text-sm font-medium">All devices</h3>
              <Button variant="outline" onClick={(event) => open(event, 'sign-out-all')}>Sign out everywhere</Button>
            </div>
          </div>
        </section>
      </div>

      {action && <AccountSecurityDialog action={action} trigger={trigger} onClose={() => setAction(null)} />}
    </div>
  );
}
