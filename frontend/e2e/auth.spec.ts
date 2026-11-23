import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

const password = 'a long and secure example password';
const owner = { id: 'owner-id', email: 'owner@example.com', verified: true };
const organization = {
  id: 'org-id',
  name: 'Example team',
  role: 'owner',
  locked: false,
};
const codes = Array.from(
  { length: 10 },
  (_, i) => `recovery-code-${i}-keep-this-secret`
);
const qr =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB1kAAAAASUVORK5CYII=';

async function mockApi(page: Page, initial = 'anonymous') {
  const state = {
    phase: initial,
    email: owner.email,
    role: 'owner',
    mfa: initial === 'mfa_challenge_required',
    jobReads: 0,
    mutations: [] as string[],
  };
  const session = () => ({
    state: state.phase,
    csrf_token: 'csrf-browser-test',
    user:
      state.phase === 'anonymous'
        ? null
        : { ...owner, email: state.email, id: state.email },
    organization:
      state.phase === 'anonymous' || state.email.includes('unassigned')
        ? null
        : { ...organization, role: state.role },
    mfa_enabled: state.mfa,
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(
      '/api/v1/',
      ''
    );
    const method = route.request().method();
    const body = method === 'POST' ? route.request().postDataJSON() : {};
    const json = (data: unknown, status = 200) =>
      route.fulfill({ status, json: data });
    if (method !== 'GET') {
      state.mutations.push(path);
      expect(route.request().headers()['origin']).toBe('http://127.0.0.1:4174');
      expect(route.request().headers()['x-csrf-token']).toBe(
        'csrf-browser-test'
      );
    }
    if (path === 'auth/session') return json(session());
    if (
      path === 'auth/register' ||
      path === 'auth/resend-verification' ||
      path === 'auth/forgot-password'
    )
      return json(
        {
          detail:
            'If this request can be completed, an email will arrive shortly.',
        },
        202
      );
    if (path === 'auth/verify-email')
      return json({ detail: 'Email verified. Sign in to continue.' });
    if (path === 'auth/login') {
      state.email = body.email;
      state.phase = state.mfa ? 'mfa_challenge_required' : 'authenticated';
      state.role = state.email.startsWith('member') ? 'member' : 'owner';
      return json(session());
    }
    if (path === 'auth/mfa/enroll')
      return json({
        uri: 'otpauth://totp/TalentMatch?secret=ABCDEFGHIJKLMNOP&issuer=TalentMatch',
        qr_code: qr,
      });
    if (path === 'auth/mfa/confirm') {
      state.phase = 'authenticated';
      state.mfa = true;
      return json({ ...session(), recovery_codes: codes });
    }
    if (path === 'auth/mfa/challenge') {
      state.phase = 'authenticated';
      return json(session());
    }
    if (path === 'auth/mfa/disable') {
      state.mfa = false;
      return json(session());
    }
    if (path === 'auth/accept-invitation') {
      state.phase = 'authenticated';
      state.role = 'member';
      state.email = 'member@example.com';
      return json(session());
    }
    if (path === 'auth/logout' || path === 'auth/logout-all') {
      state.phase = 'anonymous';
      return route.fulfill({ status: 204 });
    }
    if (path === 'job-descriptions') {
      state.jobReads += 1;
      if (state.phase !== 'authenticated')
        return json(
          { title: 'session_expired', detail: 'Please sign in.' },
          401
        );
      return json({
        items: [
          {
            id: 'job-id',
            title: `Private job for ${state.email}`,
            company: 'Example',
            file_type: 'pdf',
            injection_scan_passed: true,
          },
        ],
        total: 1,
      });
    }
    if (path === 'dashboard/candidates/resume-id/job/job-id')
      return json({
        resume_id: 'resume-id',
        filename: 'resume.docx',
        file_type: 'docx',
        candidate_name: 'Candidate',
        injection_scan_passed: true,
      });
    if (path.endsWith('/resume-file'))
      return route.fulfill({
        status: 200,
        body: 'private resume',
        headers: {
          'Content-Disposition': 'attachment; filename="resume.docx"',
          'Content-Type': 'application/octet-stream',
        },
      });
    if (path === 'organization/members')
      return json([{ ...owner, role: 'owner' }]);
    if (path === 'organization/invitations') return json([]);
    return json({ detail: `Unexpected API path ${path}` }, 404);
  });
  return state;
}

async function login(page: Page, email: string) {
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
}

test('owner signs in without MFA and can enable it from Account security', async ({
  page,
}) => {
  const state = await mockApi(page);
  await page.goto('/signup');
  await page.getByLabel('Email', { exact: true }).fill(owner.email);
  await page.getByLabel('Organization name').fill('Example team');
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Create your organization' }).click();
  await expect(page.getByRole('status')).toContainText('an email will arrive');
  await page.goto('/verify-email#token=private-verification-token');
  await page.getByRole('button', { name: 'Verify your email' }).click();
  await expect(page.getByRole('status')).toContainText('Email verified');
  expect(page.url()).not.toContain('token');
  await page.getByRole('link', { name: 'Sign in', exact: true }).click();
  await login(page, owner.email);
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await page.goto('/mfa?returnTo=%2FMFA%2F');
  await expect(page).toHaveURL('http://127.0.0.1:4174/');
  await expect(
    page.getByRole('button', { name: 'Set up authenticator' })
  ).toHaveCount(0);
  expect(state.mutations.some((path) => path.startsWith('auth/mfa/'))).toBe(false);
  await page.setViewportSize({ width: 320, height: 800 });
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Account security' }).click();
  const security = page.getByRole('region', { name: 'Two-factor authentication' });
  await expect(security.getByText('Off', { exact: true })).toBeVisible();
  await security.getByRole('button', { name: 'Enable authenticator' }).click();
  await security.getByLabel('Current password').fill(password);
  await page.getByRole('button', { name: 'Set up authenticator' }).click();
  await expect(
    page.getByAltText('Scan this QR code with your authenticator app')
  ).toBeVisible();
  await page.getByLabel('Authentication code', { exact: true }).fill('123456');
  await page.getByRole('button', { name: 'Confirm authenticator' }).click();
  await expect(security.getByText('On', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Recovery codes', { exact: true })).toHaveValue(
    codes.join('\n')
  );
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(
    page.getByLabel('Recovery codes', { exact: true })
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Continue' })).toBeDisabled();
  await page.getByLabel('I saved my recovery codes').check();
  await page.getByRole('button', { name: 'Continue' }).click();
  const turnOff = security.getByRole('button', { name: 'Turn off two-factor authentication' });
  await expect(turnOff).toBeDisabled();
  await security.getByLabel('Current password').fill(password);
  await security.getByLabel('Authenticator or recovery code').fill(codes[0]);
  await turnOff.click();
  await expect(security.getByText('Off', { exact: true })).toBeVisible();
  await page.getByRole('main')
    .getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Sign in', exact: true })
  ).toBeVisible();
});

test('protected routes wait for the session and preserve the requested destination', async ({
  page,
}) => {
  const state = await mockApi(page);
  await page.goto('/jobs');
  await expect(page).toHaveURL(/\/login\?returnTo=%2Fjobs/);
  expect(state.jobReads).toBe(0);
  await login(page, 'member@example.com');
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(
    page.getByText('Private job for member@example.com')
  ).toBeVisible();
});

test('logging in as another user clears cached hiring data', async ({
  page,
}) => {
  const state = await mockApi(page);
  await page.goto('/login?returnTo=%2Fjobs');
  await login(page, 'member-alice@example.com');
  await expect(
    page.getByText('Private job for member-alice@example.com')
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await login(page, 'member-bob@example.com');
  await page.getByRole('link', { name: 'Jobs', exact: true }).click();
  await expect(
    page.getByText('Private job for member-bob@example.com')
  ).toBeVisible();
  await expect(
    page.getByText('Private job for member-alice@example.com')
  ).toHaveCount(0);
  expect(state.jobReads).toBeGreaterThanOrEqual(2);
});

test('invitation acceptance and protected file downloads work for members', async ({
  page,
}) => {
  await mockApi(page);
  await page.goto('/accept-invitation#token=private-invitation-token');
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Accept invitation' }).click();
  await expect(
    page.getByRole('heading', { name: 'Dashboard', exact: true })
  ).toBeVisible();
  await page.goto('/candidates/resume-id/job/job-id');
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download', exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe('resume.docx');
});

test('MFA challenges gate requests and an external return URL is rejected', async ({
  page,
}) => {
  const state = await mockApi(page, 'mfa_challenge_required');
  await page.goto('/mfa?returnTo=https%3A%2F%2Fevil.example');
  await page.getByLabel('Authenticator or recovery code').fill(codes[0]);
  expect(state.jobReads).toBe(0);
  await page.getByRole('button', { name: 'Verify', exact: true }).click();
  await expect(page).toHaveURL('http://127.0.0.1:4174/');
  await expect(
    page.getByRole('heading', { name: 'Dashboard', exact: true })
  ).toBeVisible();
});

test('an existing user without an organization returns to their invitation after login', async ({
  page,
}) => {
  await mockApi(page);
  await page.goto('/accept-invitation#token=private-invitation-token');
  await page
    .getByRole('link', { name: 'Sign in to the invited account' })
    .click();
  expect(page.url()).not.toContain('token');
  await login(page, 'member-unassigned@example.com');
  await expect(
    page.getByRole('heading', { name: 'Join your team' })
  ).toBeVisible();
  await page.getByRole('button', { name: 'Accept invitation' }).click();
  await expect(
    page.getByRole('heading', { name: 'Dashboard', exact: true })
  ).toBeVisible();
});
