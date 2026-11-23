import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { SessionState } from '../src/types/auth';

const email = 'owner@example.com';
const password = 'a long and secure example password';
const token = 'private-verification-token';
const verificationUrl = `/verify-email#token=${token}`;
const genericEmail = { detail: 'If this request can be completed, an email will arrive shortly.' };

async function mockVerification(page: Page, phase: SessionState = 'anonymous') {
  const state = {
    phase,
    verified: false,
    requests: [] as string[],
    registrationStatus: 202,
    registerWait: Promise.resolve(),
    verificationWait: Promise.resolve(),
    resendLimited: false,
    verificationLimited: false,
    verificationError: '',
    workspaceReads: 0,
  };
  const session = () => ({
    state: state.phase,
    csrf_token: 'csrf-verification',
    user: state.phase === 'anonymous' ? null : { id: 'owner', email, verified: state.verified },
    organization: state.phase === 'authenticated' ? { id: 'org', name: 'Hiring team', role: 'owner', locked: false } : null,
    mfa_enabled: state.phase === 'mfa_challenge_required',
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1/', '');
    if (request.method() === 'POST') {
      state.requests.push(path);
      expect(request.headers()['x-csrf-token']).toBe('csrf-verification');
      expect(request.headers()['origin']).toBe('http://127.0.0.1:4174');
    }
    if (path === 'auth/session') return route.fulfill({ json: session() });
    if (path === 'auth/register') {
      expect(request.postDataJSON()).toEqual({ email, password, organization_name: 'Hiring team' });
      await state.registerWait;
      return route.fulfill({
        status: state.registrationStatus,
        json: state.registrationStatus === 202 ? genericEmail : { detail: 'Try again shortly.' },
      });
    }
    if (path === 'auth/resend-verification') {
      expect(request.postDataJSON()).toEqual({ email });
      if (state.resendLimited)
        return route.fulfill({
          status: 429,
          headers: { 'Retry-After': '120' },
          json: { title: 'rate_limited', detail: 'Too many attempts. Try again later.' },
        });
      return route.fulfill({ status: 202, json: genericEmail });
    }
    if (path === 'auth/verify-email') {
      expect(request.postDataJSON()).toEqual({ token });
      await state.verificationWait;
      if (state.verificationLimited)
        return route.fulfill({
          status: 429,
          headers: { 'Retry-After': '30' },
          json: { title: 'rate_limited', detail: 'Too many attempts. Try again later.' },
        });
      if (state.verificationError)
        return route.fulfill({
          status: state.verificationError === 'auth_unavailable' ? 503 : 400,
          json: { title: state.verificationError, detail: 'Verification could not be completed.' },
        });
      const result = state.verified ? 'already_verified' : 'verified';
      state.verified = true;
      if (state.phase === 'email_verification_required') state.phase = 'anonymous';
      return route.fulfill({ json: { status: result } });
    }
    if (path === 'auth/login') {
      expect(request.postDataJSON()).toEqual({ email, password });
      state.phase = state.verified ? 'authenticated' : 'email_verification_required';
      return route.fulfill({ json: session() });
    }
    if (path === 'auth/logout') {
      state.phase = 'anonymous';
      return route.fulfill({ status: 204 });
    }
    if (path === 'job-descriptions') {
      state.workspaceReads += 1;
      return route.fulfill({ json: { items: [], total: 0 } });
    }
    return route.fulfill({ status: 404, json: { detail: `Unexpected request: ${path}` } });
  });
  return state;
}

test('registration leads to a reload-safe verification result and sign-in', async ({ page }) => {
  const state = await mockVerification(page);
  const register = Promise.withResolvers<void>();
  state.registerWait = register.promise;
  await page.goto('/signup');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Organization name').fill('Hiring team');
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Create your organization' }).click();
  await expect(page.getByRole('button', { name: 'Creating organization…' })).toBeDisabled();
  await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
  register.resolve();
  await expect(page).toHaveURL(/\/verify-email\/pending$/);
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeFocused();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Resend in/ })).toBeDisabled();
  expect(state.requests).toEqual(['auth/register']);

  await page.goto(verificationUrl);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Verify your email' })).toBeVisible();
  expect(state.requests).toEqual(['auth/register']);
  const verify = Promise.withResolvers<void>();
  state.verificationWait = verify.promise;
  await page.getByRole('button', { name: 'Verify email' }).click();
  await expect(page.getByRole('button', { name: 'Verifying…' })).toBeDisabled();
  await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
  verify.resolve();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeFocused();
  await expect(page).toHaveURL(/\/verify-email$/);
  await expect(page.getByRole('button', { name: 'Verify email' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Request a new link' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  expect(state.requests).toEqual(['auth/register', 'auth/verify-email']);
  expect(state.workspaceReads).toBe(0);

  await page.goto(verificationUrl);
  await page.getByRole('button', { name: 'Verify email' }).click();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await page.getByRole('link', { name: 'Sign in' }).click();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await page.getByRole('link', { name: 'Sign in' }).click();
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});

test('registration errors preserve the entered details and the account link preserves returnTo', async ({ page }) => {
  const state = await mockVerification(page);
  state.registrationStatus = 503;
  await page.goto('/signup?returnTo=%2Fjobs');
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login?returnTo=%2Fjobs');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Organization name').fill('Hiring team');
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Create your organization' }).click();
  await expect(page.getByRole('alert')).toHaveText('Try again shortly.');
  await expect(page.getByLabel('New password')).toHaveValue(password);
  await expect(page.getByLabel('Organization name')).toHaveValue('Hiring team');
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue(email);
  state.registrationStatus = 202;
  await page.getByRole('button', { name: 'Create your organization' }).click();
  await expect(page).toHaveURL(/\/verify-email\/pending\?returnTo=%2Fjobs$/);
});

test('receiving a link again respects cooldowns and server throttling', async ({ page }) => {
  const state = await mockVerification(page);
  await page.clock.install();
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto('/verify-email');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByRole('button', { name: 'Send verification link' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await expect(page.getByText(/If you receive a verification email/)).toBeVisible();
  await expect(page.getByRole('status')).toContainText('New link requested');
  await expect(page.getByRole('button', { name: /Resend in/ })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: /Resend in/ })).toBeDisabled();
  expect(await page.locator('body').evaluate((body) => body.scrollWidth)).toBe(320);
  await page.clock.fastForward(61_000);
  state.resendLimited = true;
  await page.getByRole('button', { name: 'Resend verification email' }).click();
  await expect(page.getByRole('alert')).toContainText('Too many attempts');
  await expect(page.getByRole('button', { name: /Try again in 11\d|Try again in 120/ })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.clock.fastForward(121_000);
  state.resendLimited = false;
  await page.getByRole('button', { name: 'Resend verification email' }).click();
  await expect(page.getByRole('status')).toContainText('New link requested');
  expect(state.requests).toEqual(Array(3).fill('auth/resend-verification'));
});

test('verification throttling survives reload without consuming the token', async ({ page }) => {
  const state = await mockVerification(page);
  await page.clock.install();
  state.verificationLimited = true;
  await page.goto(verificationUrl);
  await page.getByRole('button', { name: 'Verify email' }).click();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await expect(page).toHaveURL(/#token=/);
  expect(state.requests).toEqual(['auth/verify-email']);
  state.verificationLimited = false;
  await page.clock.fastForward(31_000);
  await page.getByRole('button', { name: 'Verify email' }).click();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
});

for (const [code, heading] of [
  ['expired_token', 'This link has expired'],
  ['invalid_token', 'This link is invalid'],
  ['used_token', 'This link is no longer active'],
]) {
  test(`${code} reaches a terminal recovery screen`, async ({ page }) => {
    const state = await mockVerification(page);
    state.verificationError = code;
    await page.goto(verificationUrl);
    await page.getByRole('button', { name: 'Verify email' }).click();
    await expect(page.getByRole('heading', { name: heading })).toBeFocused();
    await page.reload();
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Verify email' })).toHaveCount(0);
    expect(state.requests).toEqual(['auth/verify-email']);
    await page.getByRole('link', { name: 'Request a new link' }).click();
    await expect(page.getByRole('heading', { name: 'Request a verification link' })).toBeVisible();
  });
}

test('temporary verification failures support retry with the original link', async ({ page }) => {
  const state = await mockVerification(page);
  state.verificationError = 'auth_unavailable';
  await page.goto(verificationUrl);
  await page.getByRole('button', { name: 'Verify email' }).click();
  await expect(page.getByRole('alert')).toContainText('Verification could not be completed.');
  await expect(page).toHaveURL(/#token=/);
  state.verificationError = '';
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
});

test('incomplete sessions retain the protected destination but still need a fresh sign-in', async ({ page }) => {
  const state = await mockVerification(page);
  await page.goto('/jobs');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/verify-email\/pending\?returnTo=%2Fjobs$/);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  expect(state.workspaceReads).toBe(0);
  await page.goto(`/verify-email?returnTo=%2Fjobs#token=${token}`);
  await page.getByRole('button', { name: 'Verify email' }).click();
  await page.getByRole('link', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/login\?returnTo=%2Fjobs$/);
  expect(state.phase).toBe('anonymous');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/jobs$/);
});

test('a direct pending visit survives throttling and can sign out', async ({ page }) => {
  const state = await mockVerification(page, 'email_verification_required');
  state.resendLimited = true;
  await page.goto('/verify-email/pending?returnTo=%2Fjobs');
  await page.getByRole('button', { name: 'Resend verification email' }).click();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.reload();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login\?returnTo=%2Fjobs$/);
  expect(state.requests).toEqual(['auth/resend-verification', 'auth/logout']);
  expect(state.workspaceReads).toBe(0);
});

test('an existing authenticated visitor can continue to their workspace', async ({ page }) => {
  const state = await mockVerification(page, 'authenticated');
  state.verified = true;
  await page.goto(verificationUrl);
  await page.getByRole('button', { name: 'Verify email' }).click();
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await page.getByRole('link', { name: 'Open workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
