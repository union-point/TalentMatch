import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export interface AuthenticatorSetup {
  uri: string;
  qr_code: string;
}

export function AuthenticatorPairing({ setup, disabled }: {
  setup: AuthenticatorSetup;
  disabled: boolean;
}) {
  const manualKey = new URL(setup.uri).searchParams.get('secret');

  return (
    <div className="flex flex-col gap-4">
      <img
        src={setup.qr_code}
        alt="Scan this QR code with your authenticator app"
        width={160}
        height={160}
        className="mx-auto size-40 rounded-lg border bg-white p-1"
      />
      <details className="rounded-lg border bg-background px-3 py-2">
        <summary className="cursor-pointer font-medium">Manual setup key</summary>
        <p className="mt-2 select-all break-all font-mono text-sm">{manualKey}</p>
      </details>
      <label className="flex flex-col gap-1.5 font-medium">
        Authentication code
        <Input
          name="code"
          autoComplete="one-time-code"
          inputMode="numeric"
          pattern="[0-9]{6}"
          placeholder="Enter 6-digit code"
          maxLength={6}
          disabled={disabled}
          required
        />
      </label>
    </div>
  );
}

export function RecoveryCodes({ codes, saved, onSavedChange }: {
  codes: string[];
  saved: boolean;
  onSavedChange: (saved: boolean) => void;
}) {
  const [copyResult, setCopyResult] = useState<'copied' | 'failed' | null>(null);
  const text = codes.join('\n');

  async function copyCodes() {
    try {
      await navigator.clipboard.writeText(text);
      setCopyResult('copied');
    } catch {
      setCopyResult('failed');
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <textarea
        aria-label="Recovery codes"
        className="w-full resize-none rounded-lg border bg-muted/50 p-3 font-mono text-sm leading-6"
        readOnly
        rows={Math.min(codes.length, 10)}
        spellCheck={false}
        value={text}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" size="sm" onClick={() => void copyCodes()}>
          Copy codes
        </Button>
        {copyResult === 'copied' && <p role="status" className="text-muted-foreground">Codes copied.</p>}
        {copyResult === 'failed' && <p role="alert">Select and copy the codes from the list.</p>}
      </div>
      <label className="flex min-h-8 items-center gap-2 font-medium">
        <input type="checkbox" checked={saved} onChange={(event) => onSavedChange(event.target.checked)} />
        I saved my recovery codes
      </label>
    </div>
  );
}
