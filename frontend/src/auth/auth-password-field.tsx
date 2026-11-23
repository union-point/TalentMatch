import { useState } from 'react';
import type { ReactNode } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Input } from '@/components/ui/input';

export function AuthPasswordField({
  value,
  onChange,
  current = false,
  required = true,
  readOnly = false,
  action,
}: {
  value: string;
  onChange: (value: string) => void;
  current?: boolean;
  required?: boolean;
  readOnly?: boolean;
  action?: ReactNode;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-1">
      <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
        <label htmlFor="auth-password">
          {current ? 'Password' : required ? 'New password' : 'New password (new accounts only)'}
        </label>
        {action}
      </div>
      <div className="relative">
        <Input
          id="auth-password"
          type={visible ? 'text' : 'password'}
          name="password"
          className="pr-12"
          placeholder={current ? 'Enter your password' : 'Choose a password'}
          autoComplete={current ? 'current-password' : 'new-password'}
          aria-describedby={current ? undefined : 'auth-password-requirements'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          minLength={current ? 1 : 15}
          maxLength={128}
          required={required}
          readOnly={readOnly}
        />
        <button
          type="button"
          className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground"
          aria-label={visible ? 'Hide password' : 'Show password'}
          onClick={() => setVisible(!visible)}
        >
          {visible ? <EyeOff size={17} aria-hidden /> : <Eye size={17} aria-hidden />}
        </button>
      </div>
      {!current && (
        <p id="auth-password-requirements" className="text-xs text-muted-foreground">
          Use at least 15 characters. Spaces are welcome.
        </p>
      )}
    </div>
  );
}
