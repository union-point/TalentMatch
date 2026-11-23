import type { AuthSession } from '../types/auth.ts';

export const verificationPath = '/verify-email';
export const pendingVerificationPath = '/verify-email/pending';
export const verificationResendDelayMs = 60_000;

export function withReturnTo(path: string, returnTo: string): string {
  return returnTo === '/' ? path : `${path}?returnTo=${encodeURIComponent(returnTo)}`;
}

export function safeReturnTo(value: string | null | undefined): string {
  if (
    !value ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\') ||
    Array.from(value).some((character) => character.charCodeAt(0) <= 32)
  )
    return '/';
  let pathname: string;
  try {
    pathname = decodeURI(new URL(value, 'https://app.invalid').pathname)
      .replace(/\/+$/, '')
      .toLowerCase();
  } catch {
    return '/';
  }
  if (
    [
      '/login',
      '/signup',
      '/mfa',
      verificationPath,
      pendingVerificationPath,
      '/forgot-password',
      '/reset-password',
    ].includes(pathname)
  )
    return '/';
  return value;
}

export function sessionDestination(
  session: AuthSession | null,
  returnTo = '/'
): string {
  if (!session || session.state === 'anonymous')
    return `/login?returnTo=${encodeURIComponent(safeReturnTo(returnTo))}`;
  if (session.state === 'email_verification_required')
    return withReturnTo(pendingVerificationPath, safeReturnTo(returnTo));
  if (session.state === 'mfa_challenge_required')
    return `/mfa?returnTo=${encodeURIComponent(safeReturnTo(returnTo))}`;
  if (!session.organization || session.organization.locked) {
    const destination = safeReturnTo(returnTo);
    if (
      !session.organization &&
      destination.split(/[?#]/)[0] === '/accept-invitation'
    )
      return destination;
    return '/account';
  }
  return safeReturnTo(returnTo);
}
