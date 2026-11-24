import { expect, test } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

const password = 'a long and secure example password';
const nextPassword = 'a different long and secure password';
const qr = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB1kAAAAASUVORK5CYII=';
const codes = Array.from({ length: 10 }, (_, i) => `sample-recovery-code-${i}`);

async function mockAccount(page: Page) {
  const state = {
    active: true,
    csrf: 1,
    requests: [] as { path: string; body: unknown }[],
    handle: async (_route: Route, _path: string): Promise<boolean> => false,
    sessionUnavailable: false,
    sessionReads: 0,
  };
  const session = () => ({
    state: state.active ? 'authenticated' : 'anonymous',
    csrf_token: 'csrf-settings-' + state.csrf,
    user: state.active ? { id: 'user', email: 'person@example.com', verified: true } : null,
    organization: null,
    mfa_enabled: state.active,
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1/', '');
    if (path === 'auth/session') {
      state.sessionReads++;
      if (state.sessionUnavailable)
        return route.fulfill({ status: 503, json: { detail: 'Session unavailable' } });
      return route.fulfill({ json: session() });
    }
    if (request.method() === 'POST') {
      expect(request.headers()['x-csrf-token']).toBe(session().csrf_token);
      expect(request.headers()['origin']).toBe('http://127.0.0.1:4174');
      state.requests.push({ path, body: request.postDataJSON() });
    }
    if (await state.handle(route, path)) return;
    if (path === 'auth/change-password') {
      state.csrf++;
      return route.fulfill({ json: session() });
    }
    if (path === 'auth/mfa/enroll')
      return route.fulfill({ json: { uri: 'otpauth://totp/TalentMatch?secret=ABCDEFGHIJKLMNOP', qr_code: qr } });
    if (path === 'auth/mfa/confirm' || path === 'auth/mfa/recovery-codes') {
      state.csrf++;
      return route.fulfill({ json: { ...session(), recovery_codes: codes } });
    }
    if (path === 'auth/logout-all' || path === 'auth/logout') {
      state.active = false;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ status: 404, json: { detail: 'Unexpected endpoint' } });
  });
  return state;
}

async function manageTwoFactor(page: Page, action: string) {
  await page.getByRole('button', { name: 'Manage two-factor authentication' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: action, exact: true }).click();
  return dialog;
}

test('password change keeps reauthentication and failures in its own dialog', async ({ page }) => {
  const state = await mockAccount(page);
  await page.goto('/account');
  await expect(page.getByRole('heading', { name: 'Account security' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Password' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Two-factor authentication' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Sessions' })).toBeVisible();
  await expect(page.getByText(/open a team invitation/i)).toBeVisible();
  await expect(page.getByLabel('Current password')).toHaveCount(0);

  const trigger = page.getByRole('region', { name: 'Password', exact: true })
    .getByRole('button', { name: 'Change password' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Change password' });
  await expect(dialog.getByRole('heading')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();

  await trigger.click();
  await dialog.getByLabel('Current password').fill(password);
  await dialog.getByLabel('New password').fill(nextPassword);
  const hold = Promise.withResolvers<void>();
  state.handle = async (route) => {
    await hold.promise;
    await route.fulfill({ status: 401, json: { title: 'invalid_credentials', detail: 'The password is incorrect.' } });
    return true;
  };
  await dialog.getByRole('button', { name: 'Change password' }).click();
  await expect(dialog.getByRole('button', { name: 'Changing password…' })).toBeDisabled();
  await dialog.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
  hold.resolve();

  await expect(dialog.getByRole('alert')).toHaveText('The password is incorrect.');
  await expect(dialog.getByLabel('New password')).toHaveValue(nextPassword);
  state.handle = async () => false;
  await dialog.getByRole('button', { name: 'Change password' }).click();
  const success = page.getByRole('dialog', { name: 'Password changed' });
  await expect(success.getByRole('heading')).toBeFocused();
  await expect(success.getByLabel('Current password')).toHaveCount(0);
  await expect(success.getByText('Your other sessions have been signed out.')).toBeVisible();
  await success.getByRole('button', { name: 'Done' }).click();
  await expect(trigger).toBeFocused();
  expect(state.requests).toEqual(Array(2).fill({
    path: 'auth/change-password', body: { password, new_password: nextPassword },
  }));
});

test('replacement and regeneration keep codes private to an acknowledged receipt', async ({ page }) => {
  const state = await mockAccount(page);
  await page.setViewportSize({ width: 320, height: 520 });
  await page.goto('/account');
  const dialog = await manageTwoFactor(page, 'Replace authenticator');
  await dialog.getByLabel('Current password').fill(password);
  await dialog.getByLabel('Authenticator or recovery code').fill(' 123456 ');
  await dialog.getByRole('button', { name: 'Set up replacement' }).click();
  await expect(dialog.getByRole('heading', { name: 'Set up your authenticator' })).toBeFocused();
  await dialog.getByText('Manual setup key', { exact: true }).click();
  await expect(dialog.getByText('ABCDEFGHIJKLMNOP')).toBeVisible();
  await expect(dialog.getByLabel('Current password')).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Start over' }).click();
  await expect(dialog.getByLabel('Current password')).toBeEmpty();
  await dialog.getByLabel('Current password').fill(password);
  await dialog.getByLabel('Authenticator or recovery code').fill('234567');
  await dialog.getByRole('button', { name: 'Set up replacement' }).click();
  await dialog.getByLabel('Authentication code', { exact: true }).fill('345678');
  await dialog.getByRole('button', { name: 'Confirm authenticator' }).click();
  await expect(dialog.getByLabel('Recovery codes', { exact: true })).toHaveValue(codes.join('\n'));
  await expect(dialog.getByText(/Your replacement authenticator is ready/)).toBeVisible();
  const priorReads = state.sessionReads;
  state.sessionUnavailable = true;
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect.poll(() => state.sessionReads).toBeGreaterThan(priorReads);
  await page.keyboard.press('Escape');
  await expect(dialog.getByLabel('Recovery codes', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Done' })).toBeDisabled();
  await dialog.getByLabel('I saved my recovery codes').check();
  await dialog.getByRole('button', { name: 'Done' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText('Couldn’t refresh your session.')).toBeVisible();
  state.sessionUnavailable = false;
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('Couldn’t refresh your session.')).toHaveCount(0);
  await expect(page.getByLabel('Recovery codes', { exact: true })).toHaveCount(0);

  await manageTwoFactor(page, 'Regenerate recovery codes');
  await expect(dialog.getByText(/replaces all your existing recovery codes/)).toBeVisible();
  await dialog.getByLabel('Current password').fill(password);
  await dialog.getByLabel('Authenticator or recovery code').fill('456789');
  await dialog.getByRole('button', { name: 'Regenerate recovery codes' }).click();
  await expect(dialog.getByText(/Your previous recovery codes have been replaced/)).toBeVisible();
  await dialog.getByLabel('I saved my recovery codes').check();
  await dialog.getByRole('button', { name: 'Done' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByLabel('Recovery codes', { exact: true })).toHaveCount(0);
  expect(await page.locator('body').evaluate((body) => body.scrollWidth)).toBe(320);
  expect(state.requests).toEqual([
    { path: 'auth/mfa/enroll', body: { password, code: '123456' } },
    { path: 'auth/mfa/enroll', body: { password, code: '234567' } },
    { path: 'auth/mfa/confirm', body: { code: '345678' } },
    { path: 'auth/mfa/recovery-codes', body: { password, code: '456789' } },
  ]);
});

test('signing out everywhere requires confirmation and retries an error without losing context', async ({ page }) => {
  const state = await mockAccount(page);
  await page.goto('/account');
  const trigger = page.getByRole('region', { name: 'Sessions' })
    .getByRole('button', { name: 'Sign out everywhere' });
  const dialog = page.getByRole('dialog', { name: 'Sign out everywhere?' });
  await trigger.click();
  await expect(dialog.getByText(/including the one on this device/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(trigger).toBeFocused();
  expect(state.requests).toHaveLength(0);

  state.handle = async (route) => {
    await route.fulfill({ status: 503, json: { detail: 'Could not sign out. Try again.' } });
    return true;
  };
  await trigger.click();
  await dialog.getByRole('button', { name: 'Sign out everywhere' }).click();
  await expect(dialog.getByRole('alert')).toHaveText('Could not sign out. Try again.');
  await expect(page).toHaveURL(/\/account$/);
  state.handle = async () => false;
  await dialog.getByRole('button', { name: 'Sign out everywhere' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByText('You’ve signed out on all devices.')).toBeVisible();
  expect(state.requests.map(({ path }) => path)).toEqual(['auth/logout-all', 'auth/logout-all']);
});
