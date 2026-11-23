import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  safeReturnTo,
  sessionDestination,
} from '../src/lib/auth-navigation.ts';

const session = {
  state: 'authenticated',
  user: { id: 'u', email: 'u@example.com', verified: true },
  organization: { id: 'o', name: 'Team', role: 'owner', locked: false },
  csrf_token: 'csrf',
  mfa_enabled: true,
};

test('return destinations only accept internal application URLs', () => {
  for (const url of [
    'https://evil.example',
    '//evil.example',
    '/\\evil.example',
    '/login',
    '/mfa',
    '/verify-email/pending',
    '/MFA/',
    '/%6dfa',
    '/jobs/../mfa',
    '/ bad',
    '/\t/evil',
    'javascript:alert(1)',
    null,
  ])
    assert.equal(safeReturnTo(url), '/');
  assert.equal(safeReturnTo('/jobs/123?page=2'), '/jobs/123?page=2');
});

test('anonymous and incomplete sessions cannot access hiring routes', () => {
  assert.equal(
    sessionDestination(null, '/jobs/123'),
    '/login?returnTo=%2Fjobs%2F123'
  );
  assert.equal(
    sessionDestination({ ...session, state: 'email_verification_required' }, '/jobs/123'),
    '/verify-email/pending?returnTo=%2Fjobs%2F123'
  );
  assert.equal(
    sessionDestination({ ...session, state: 'mfa_challenge_required' }),
    '/mfa?returnTo=%2F'
  );
});

test('organization-less and locked memberships lead to account settings', () => {
  assert.equal(
    sessionDestination({ ...session, organization: null }),
    '/account'
  );
  assert.equal(
    sessionDestination({
      ...session,
      organization: { ...session.organization, locked: true },
    }),
    '/account'
  );
  assert.equal(
    sessionDestination({ ...session, mfa_enabled: false }, '/jobs'),
    '/jobs'
  );
});

test('a signed-in user without membership can return to an invitation', () => {
  assert.equal(
    sessionDestination(
      { ...session, organization: null },
      '/accept-invitation'
    ),
    '/accept-invitation'
  );
});
