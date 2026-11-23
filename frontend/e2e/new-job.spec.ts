import { test, expect, type Page } from '@playwright/test';

const organization = { id: 'org-1', name: 'Example Team', role: 'owner', locked: false };
const job = { id: 'job-1', title: 'Product Designer', company: organization.name, file_type: 'txt' };

async function mockJobs(page: Page, failFirst = false) {
  const uploads: string[] = [];
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/job-descriptions/upload')) {
      uploads.push(route.request().postDataBuffer()?.toString('utf8') ?? '');
      return failFirst && uploads.length === 1
        ? route.fulfill({ status: 503, json: { detail: 'Please try again.' } })
        : route.fulfill({ json: job });
    }
    if (path.endsWith('/auth/session')) return route.fulfill({ json: {
      state: 'authenticated', csrf_token: 'test-csrf', mfa_enabled: true,
      user: { id: 'user-1', email: 'recruiter@example.com', verified: true },
      organization,
    } });
    if (path.endsWith('/job-descriptions/job-1')) return route.fulfill({ json: job });
    return route.fulfill({ json: { items: [], total: 0, page: 1, pages: 0 } });
  });
  return uploads;
}

test('new job keeps both drafts and submits the active source after a failure', async ({ page }) => {
  const uploads = await mockJobs(page, true);
  await page.goto('/jobs');
  await page.getByRole('button', { name: 'New job' }).click();
  const dialog = page.getByRole('dialog', { name: 'New job' });
  const create = dialog.getByRole('button', { name: 'Create vacancy' });
  const description = dialog.getByRole('textbox', { name: 'Job description', exact: true });

  await expect.poll(async () => (await dialog.boundingBox())?.width ?? 0).toBeGreaterThan(448);
  await expect(create).toBeDisabled();
  await dialog.getByLabel('Job title').fill(job.title);
  await expect(dialog.getByLabel('Company')).toHaveValue(organization.name);
  await description.fill('Résumé review and design systems.');
  await dialog.getByRole('tab', { name: 'Upload file' }).click();
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'designer.markdown',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Design leadership'),
  });
  await expect(dialog.getByText('designer.markdown')).toBeVisible();

  await dialog.getByRole('tab', { name: 'Paste text' }).click();
  await expect(description).toHaveValue('Résumé review and design systems.');
  await create.click();
  await expect(dialog.getByRole('alert')).toHaveText('Please try again.');
  await expect(description).toHaveValue('Résumé review and design systems.');
  expect(uploads[0]).toContain('filename="job-description.txt"');
  expect(uploads[0]).toContain('Résumé review and design systems.');

  await dialog.getByRole('tab', { name: 'Upload file' }).click();
  await expect(dialog.getByText('designer.markdown')).toBeVisible();
  await create.click();
  await expect(page).toHaveURL(/\/jobs\/job-1$/);
  expect(uploads[1]).toContain('filename="designer.markdown"');
  expect(uploads[1]).toContain('# Design leadership');
  expect(uploads[1]).not.toContain('Résumé review');
});

test('new job keeps the action visible on a short mobile viewport and accepts dropped TXT', async ({ page }) => {
  const uploads = await mockJobs(page);
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto('/');
  const trigger = page.getByRole('button', { name: 'New job' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'New job' });
  const create = dialog.getByRole('button', { name: 'Create vacancy' });
  await expect(dialog).toBeVisible();
  await expect.poll(async () => (await dialog.boundingBox())?.width ?? 0).toBeGreaterThan(338);
  await expect.poll(async () => (await dialog.boundingBox())?.height ?? 0).toBeGreaterThan(752);

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await dialog.getByLabel('Job title').fill(job.title);
  await dialog.getByRole('textbox', { name: 'Job description', exact: true }).focus();
  await page.setViewportSize({ width: 360, height: 400 });
  await expect(create).toBeInViewport();

  await dialog.getByRole('tab', { name: 'Upload file' }).click();
  const dropZone = dialog.getByRole('group', { name: 'Job description file' });
  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['Lead product design.'], 'description.TXT', { type: 'text/plain' }));
    return transfer;
  });
  await dropZone.dispatchEvent('drop', { dataTransfer });
  await expect(dropZone.getByText('description.TXT')).toBeVisible();
  await create.click();
  await expect(page).toHaveURL(/\?jd=job-1$/);
  expect(uploads[0]).toContain('filename="description.TXT"');
});
