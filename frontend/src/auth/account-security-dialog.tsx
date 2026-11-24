import { useEffect, useRef, useState } from 'react';
import type { FormEvent, RefObject } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ChevronRight } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { AuthenticatorPairing, RecoveryCodes } from '@/auth/mfa-enrollment';
import type { AuthenticatorSetup } from '@/auth/mfa-enrollment';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ApiError, fetchPost } from '@/lib/api';
import type { AuthSession, RecoverySession } from '@/types/auth';

export type AccountSecurityAction =
  | 'password' | 'manage' | 'enable' | 'replace' | 'regenerate' | 'disable'
  | 'sign-out' | 'sign-out-all';

type View =
  | { step: AccountSecurityAction }
  | { step: 'pair'; setup: AuthenticatorSetup; replacing: boolean }
  | { step: 'codes'; codes: string[]; description: string }
  | { step: 'success'; title: string; description: string };

const content = {
  password: {
    title: 'Change password',
    description: 'Enter your current password. Your other sessions will be signed out after the change.',
    submit: 'Change password',
    pending: 'Changing password…',
  },
  manage: {
    title: 'Manage two-factor authentication',
    description: 'Use your current password and a code to make changes.',
  },
  enable: {
    title: 'Enable authenticator',
    description: 'Verify your password to connect an authenticator app.',
    submit: 'Set up authenticator',
    pending: 'Preparing setup…',
  },
  replace: {
    title: 'Replace authenticator',
    description: 'Verify your identity with your current factor. Your new authenticator and recovery codes will replace the old ones after confirmation.',
    submit: 'Set up replacement',
    pending: 'Preparing replacement…',
  },
  pair: {
    title: 'Set up your authenticator',
    description: 'Scan the QR code or enter the setup key in your authenticator app, then enter its six-digit code. Setup expires after ten minutes.',
    submit: 'Confirm authenticator',
    pending: 'Confirming authenticator…',
  },
  regenerate: {
    title: 'Regenerate recovery codes',
    description: 'This replaces all your existing recovery codes. Verify your identity to generate a new set.',
    submit: 'Regenerate recovery codes',
    pending: 'Generating codes…',
  },
  disable: {
    title: 'Turn off two-factor authentication',
    description: 'Your password alone will be enough to sign in. Recovery codes will stop working, and your other sessions will be signed out.',
    submit: 'Turn off two-factor authentication',
    pending: 'Turning off two-factor authentication…',
  },
  'sign-out': {
    title: 'Sign out of this device?',
    description: 'You’ll need to sign in again on this device. Your other sessions will stay active.',
    submit: 'Sign out',
    pending: 'Signing out…',
  },
  'sign-out-all': {
    title: 'Sign out everywhere?',
    description: 'This ends all your sessions, including the one on this device.',
    submit: 'Sign out everywhere',
    pending: 'Signing out everywhere…',
  },
};

const managementActions = [
  { step: 'replace', label: 'Replace authenticator', detail: 'Connect a new app or device.' },
  { step: 'regenerate', label: 'Regenerate recovery codes', detail: 'Replace your existing set of codes.' },
  { step: 'disable', label: 'Turn off two-factor authentication', detail: 'Return to password-only sign-in.' },
] as const;

export function AccountSecurityDialog({ action, trigger, onClose }: {
  action: AccountSecurityAction;
  trigger: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}) {
  const auth = useAuth();
  const heading = useRef<HTMLHeadingElement>(null);
  const inFlight = useRef(false);
  const [open, setOpen] = useState(true);
  const [view, setView] = useState<View>({ step: action });
  const [saved, setSaved] = useState(false);
  const { step } = view;
  const mutation = useMutation({
    gcTime: 0,
    networkMode: 'always',
    mutationFn: async (form: FormData) => {
      const password = String(form.get('password') ?? '');
      const code = String(form.get('code') ?? '').trim();

      function showCodes(result: RecoverySession, description: string) {
        const { recovery_codes: codes, ...session } = result;
        setView({ step: 'codes', codes, description });
        auth.update(session);
      }

      switch (step) {
        case 'password':
          auth.update(await fetchPost<AuthSession>('/v1/auth/change-password', {
            password, new_password: form.get('new_password'),
          }));
          setView({ step: 'success', title: 'Password changed', description: 'Your other sessions have been signed out.' });
          break;
        case 'enable':
        case 'replace': {
          const replacing = step === 'replace';
          const setup = await fetchPost<AuthenticatorSetup>('/v1/auth/mfa/enroll', {
            password, ...(replacing ? { code } : {}),
          });
          setView({ step: 'pair', setup, replacing });
          break;
        }
        case 'pair':
          showCodes(await fetchPost<RecoverySession>('/v1/auth/mfa/confirm', { code }),
            view.replacing ? 'Your replacement authenticator is ready.' : 'Two-factor authentication is on.');
          break;
        case 'regenerate':
          showCodes(await fetchPost<RecoverySession>('/v1/auth/mfa/recovery-codes', { password, code }),
            'Your previous recovery codes have been replaced.');
          break;
        case 'disable':
          auth.update(await fetchPost<AuthSession>('/v1/auth/mfa/disable', { password, code }));
          setView({ step: 'success', title: 'Two-factor authentication is off', description: 'Your other sessions have been signed out.' });
          break;
        case 'sign-out':
        case 'sign-out-all':
          await auth.logout(step === 'sign-out-all');
          window.location.replace(`/login?signedOut=${step === 'sign-out-all' ? 'everywhere' : 'device'}`);
          break;
      }
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'csrf_failed') void auth.refresh();
    },
    onSettled: () => { inFlight.current = false; },
  });
  const busy = mutation.isPending;
  const unsavedCodes = step === 'codes' && !saved;

  useEffect(() => { heading.current?.focus(); }, [step]);

  useEffect(() => {
    if (!unsavedCodes) return;
    function warn(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = '';
    }
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [unsavedCodes]);

  function move(next: AccountSecurityAction) {
    mutation.reset();
    setView({ step: next });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || busy) return;
    inFlight.current = true;
    mutation.mutate(new FormData(event.currentTarget), { onSuccess: () => mutation.reset() });
  }

  const commands = step === 'manage' || step === 'codes' || step === 'success' ? null : content[step];
  const title = step === 'codes' ? 'Save your recovery codes'
    : step === 'success' ? view.title : content[step].title;
  const description = step === 'codes'
    ? view.description + ' Save these one-time codes securely. This list is shown once. If you lose your authenticator and all your codes, you’ll lose access.'
    : step === 'success' ? view.description : content[step].description;
  const requiresCode = step === 'replace' || step === 'regenerate' || step === 'disable';
  const destructive = step === 'disable' || step === 'sign-out-all';

  return (
    <Dialog open={open} disablePointerDismissal onOpenChange={(next, details) => {
      if (!next && (inFlight.current || busy || unsavedCodes)) {
        details.cancel();
        return;
      }
      setOpen(next);
    }} onOpenChangeComplete={(next) => { if (!next) onClose(); }}>
      <DialogContent
        initialFocus={heading}
        finalFocus={trigger}
        showCloseButton={!busy && step !== 'codes'}
        className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-lg"
      >
        <DialogHeader className="shrink-0 border-b px-5 py-4 pr-12 sm:px-6 sm:pr-12">
          <DialogTitle ref={heading} tabIndex={-1} className="text-3xl font-normal leading-none focus:outline-none">
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {(step === 'manage' || step === 'codes' || commands) && (
          <div className="min-h-0 overflow-y-auto overscroll-contain px-5 py-4 sm:px-6">
            {step === 'manage' && (
              <div className="flex flex-col gap-2">
                {managementActions.map(({ step, label, detail }) => (
                  <Button key={step} type="button" variant="outline" aria-label={label}
                    aria-describedby={`account-action-${step}`}
                    className="h-auto justify-between gap-4 whitespace-normal px-3 py-3 text-left"
                    onClick={() => move(step)}>
                    <span className="flex min-w-0 flex-col gap-1">
                      {label}
                      <span id={`account-action-${step}`} className="text-xs font-normal text-muted-foreground">{detail}</span>
                    </span>
                    <ChevronRight data-icon="inline-end" aria-hidden />
                  </Button>
                ))}
              </div>
            )}
            {step === 'codes' && <RecoveryCodes codes={view.codes} saved={saved} onSavedChange={setSaved} />}
            {commands && (
              <form key={step} id="account-security-form" onSubmit={submit} aria-busy={busy} className="flex flex-col gap-4">
                {(step === 'password' || step === 'enable' || requiresCode) && (
                  <label className="flex flex-col gap-1.5 font-medium">
                    Current password
                    <Input type="password" name="password" autoComplete="current-password" maxLength={128}
                      disabled={busy} required />
                  </label>
                )}
                {step === 'password' && (
                  <div className="flex flex-col gap-1.5 font-medium">
                    <label htmlFor="account-new-password">New password</label>
                    <Input id="account-new-password" type="password" name="new_password" autoComplete="new-password"
                      minLength={15} maxLength={128} aria-describedby="account-new-password-help" disabled={busy} required />
                    <span id="account-new-password-help" className="text-xs font-normal text-muted-foreground">
                      Use at least 15 characters. Spaces are welcome.
                    </span>
                  </div>
                )}
                {requiresCode && (
                  <label className="flex flex-col gap-1.5 font-medium">
                    Authenticator or recovery code
                    <Input name="code" autoComplete="one-time-code" maxLength={128} disabled={busy} required />
                  </label>
                )}
                {step === 'pair' && <AuthenticatorPairing setup={view.setup} disabled={busy} />}
                {mutation.error && <p role="alert" className="text-destructive">
                  {mutation.error instanceof ApiError ? mutation.error.message : 'Couldn’t complete this step. Try again.'}
                </p>}
                {step === 'pair' && (
                  <button type="button" className="text-link w-fit" disabled={busy}
                    onClick={() => move(view.replacing ? 'replace' : 'enable')}>
                    Start over
                  </button>
                )}
              </form>
            )}
          </div>
        )}

        {busy && commands && <p role="status" className="sr-only">{commands.pending}</p>}
        <DialogFooter className="mx-0 mb-0 shrink-0 px-5 sm:px-6">
          {commands ? (
            <>
              <Button type="button" variant="outline" disabled={busy} onClick={() => {
                if (inFlight.current) return;
                if (requiresCode) move('manage');
                else setOpen(false);
              }}>
                {requiresCode ? 'Back' : 'Cancel'}
              </Button>
              <Button type="submit" form="account-security-form" variant={destructive ? 'destructive' : 'default'}
                className="h-auto min-h-10 whitespace-normal py-2" disabled={busy}>
                {busy ? commands.pending : commands.submit}
              </Button>
            </>
          ) : (
            <Button type="button" disabled={unsavedCodes} onClick={() => setOpen(false)}>Done</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
