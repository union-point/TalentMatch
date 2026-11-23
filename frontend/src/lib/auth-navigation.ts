import type { AuthSession } from '../types/auth.ts';

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
      '/verify-email',
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
  if (session.state === 'email_verification_required') return '/verify-email';
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
