import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const email = 'owner@example.com';
const password = 'a new long and secure password';
const token = 'private-password-reset-token';
const link = `/reset-password?returnTo=%2Fjobs#token=${token}`;

async function mockRecovery(page: Page, activeEmail: string | null = null) {
  const state = {
    activeEmail,
    requestWait: Promise.resolve(),
    resetWait: Promise.resolve(),
    requestStatus: 202,
    resetStatus: 200,
    used: false,
    requests: [] as string[],
  };
  const session = () => ({
    state: state.activeEmail ? 'authenticated' : 'anonymous',
    csrf_token: 'csrf-recovery',
    user: state.activeEmail ? { id: state.activeEmail, email: state.activeEmail, verified: true } : null,
    organization: state.activeEmail ? { id: 'org', name: 'Hiring team', role: 'owner', locked: false } : null,
    mfa_enabled: false,
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1/', '');
    if (request.method() === 'POST') {
      state.requests.push(path);
      expect(request.headers()['x-csrf-token']).toBe('csrf-recovery');
      expect(request.headers()['origin']).toBe('http://127.0.0.1:4174');
    }
    if (path === 'auth/session') return route.fulfill({ json: session() });
    if (path === 'auth/forgot-password') {
      expect(request.postDataJSON()).toEqual({ email });
      await state.requestWait;
      if (state.requestStatus === 429)
        return route.fulfill({ status: 429, headers: { 'Retry-After': '120' }, json: { title: 'rate_limited' } });
      return route.fulfill({
        status: state.requestStatus,
        json: { detail: state.requestStatus === 202
          ? 'If this request can be completed, an email will arrive shortly.'
          : 'Could not request a reset link. Try again.' },
      });
    }
    if (path === 'auth/reset-password') {
      expect(request.postDataJSON()).toEqual({ token, password });
      await state.resetWait;
      if (state.used || state.resetStatus === 400)
        return route.fulfill({ status: 400, json: { title: 'invalid_token', detail: 'This link is invalid or expired.' } });
      if (state.resetStatus === 429)
        return route.fulfill({ status: 429, headers: { 'Retry-After': '30' }, json: { title: 'rate_limited' } });
      if (state.resetStatus !== 200)
        return route.fulfill({ status: state.resetStatus, json: { detail: 'Could not update the password. Try again.' } });
      state.used = true;
      if (state.activeEmail === email) state.activeEmail = null;
      return route.fulfill({ json: { detail: 'Password reset. Sign in to continue.' } });
    }
    if (path === 'auth/login') {
      expect(request.postDataJSON()).toEqual({ email, password });
      state.activeEmail = email;
      return route.fulfill({ json: session() });
    }
    if (path === 'job-descriptions') return route.fulfill({ json: { items: [], total: 0 } });
    return route.fulfill({ status: 404, json: { detail: `Unexpected request: ${path}` } });
  });
  return state;
}

test('recovery moves through separate stages and keeps the completed result on reload and Back', async ({ page }) => {
  const state = await mockRecovery(page);
  const request = Promise.withResolvers<void>();
  state.requestWait = request.promise;
  await page.goto('/jobs');
  await page.getByRole('link', { name: 'Forgot password?' }).click();
  await expect(page).toHaveURL(/\/forgot-password\?returnTo=%2Fjobs$/);
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('button', { name: 'Requesting link…' })).toBeDisabled();
  await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
  request.resolve();

  await expect(page).toHaveURL(/\/forgot-password\/check-email\?returnTo=%2Fjobs$/);
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeFocused();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByLabel('Email', { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Resend in/ })).toBeDisabled();
  expect(state.requests).toEqual(['auth/forgot-password']);

  await page.goto(link);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible();
  const reset = Promise.withResolvers<void>();
  state.resetWait = reset.promise;
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Update password' }).click();
  await expect(page.getByRole('button', { name: 'Updating password…' })).toBeDisabled();
  await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
  reset.resolve();

  await expect(page.getByRole('heading', { name: 'Password updated' })).toBeFocused();
  await expect(page).toHaveURL(/\/reset-password\?returnTo=%2Fjobs$/);
  await expect(page.getByLabel('New password')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Update password' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Password updated' })).toBeVisible();
  expect(state.requests).toEqual(['auth/forgot-password', 'auth/reset-password']);

  await page.getByRole('link', { name: 'Sign in', exact: true }).click();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Password updated' })).toBeVisible();
  await page.getByRole('link', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/jobs$/);
});

test('request errors preserve the address and resend waits for the server cooldown', async ({ page }) => {
  const state = await mockRecovery(page);
  await page.clock.install();
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto('/forgot-password/check-email');
  await expect(page).toHaveURL(/\/forgot-password$/);
  state.requestStatus = 503;
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('alert')).toHaveText('Could not request a reset link. Try again.');
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue(email);

  state.requestStatus = 202;
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await expect(page.getByText(/If a reset link is available/)).toBeVisible();
  expect(await page.locator('body').evaluate((body) => body.scrollWidth)).toBe(320);
  await page.clock.fastForward(61_000);
  state.requestStatus = 429;
  await page.getByRole('button', { name: 'Send another link' }).click();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  state.requestStatus = 202;
  await page.clock.fastForward(121_000);
  await page.getByRole('button', { name: 'Send another link' }).click();
  await expect(page.getByRole('status')).toHaveText('New link requested.');
  await page.getByRole('link', { name: 'Use a different email' }).click();
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  expect(state.requests).toEqual(Array(4).fill('auth/forgot-password'));
});

test('an expired or consumed link replaces the form with recoverable guidance', async ({ page }) => {
  const state = await mockRecovery(page);
  for (const scenario of ['expired', 'consumed']) {
    state.resetStatus = scenario === 'expired' ? 400 : 200;
    state.used = scenario === 'consumed';
    await page.goto(link);
    await page.getByLabel('New password').fill(password);
    await page.getByRole('button', { name: 'Update password' }).click();
    await expect(page.getByRole('heading', { name: 'Reset link unavailable' })).toBeFocused();
    await expect(page).toHaveURL(/\/reset-password\?returnTo=%2Fjobs$/);
    await page.reload();
    await expect(page.getByLabel('New password')).toHaveCount(0);
    await page.getByRole('link', { name: 'Request a new link' }).click();
    await expect(page).toHaveURL(/\/forgot-password\?returnTo=%2Fjobs$/);
  }
  await page.goto('/reset-password#token=short');
  await expect(page.getByRole('heading', { name: 'Reset link unavailable' })).toBeVisible();
  await expect(page).toHaveURL(/\/reset-password$/);
  await page.goto('/reset-password?token=private-password-reset-token');
  await expect(page.getByRole('heading', { name: 'Reset link unavailable' })).toBeVisible();
  await expect(page).toHaveURL(/\/reset-password$/);
  expect(state.requests).toEqual(['auth/reset-password', 'auth/reset-password']);
});

test('a transient reset failure keeps the form and a rate limit survives reload', async ({ page }) => {
  const state = await mockRecovery(page);
  await page.clock.install();
  await page.goto(link);
  const field = page.getByLabel('New password');
  await field.fill(password);
  state.resetStatus = 503;
  await page.getByRole('button', { name: 'Update password' }).click();
  await expect(page.getByRole('alert')).toHaveText('Could not update the password. Try again.');
  await expect(field).toHaveValue(password);

  state.resetStatus = 429;
  await page.getByRole('button', { name: 'Update password' }).click();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.reload();
  await expect(page).toHaveURL(link);
  await expect(field).toBeEmpty();
  await expect(page.getByRole('button', { name: /Try again in/ })).toBeDisabled();
  await page.clock.fastForward(31_000);
  state.resetStatus = 200;
  await field.fill(password);
  await page.getByRole('button', { name: 'Update password' }).click();
  await expect(page.getByRole('heading', { name: 'Password updated' })).toBeVisible();
});

test('the reset completion opens sign-in directly even when this browser has another account', async ({ page }) => {
  const otherEmail = 'other@example.com';
  const state = await mockRecovery(page, otherEmail);
  await page.goto(link);
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Update password' }).click();
  const signIn = page.getByRole('link', { name: 'Sign in', exact: true });
  await expect(signIn).toHaveAttribute('href', '/login?returnTo=%2Fjobs&source=password-reset');
  await page.goto('/login?returnTo=%2Fjobs&source=password-reset');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByLabel('Email', { exact: true })).toBeEmpty();
  expect(state.activeEmail).toBe(otherEmail);
});
