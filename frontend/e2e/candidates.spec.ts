import { test, expect, type Page } from '@playwright/test';

const job = { id: 'job-1', title: 'Engineer', company: 'Example', file_type: 'pdf', injection_scan_passed: true };

async function mockCandidates(page: Page) {
  const requests: URLSearchParams[] = [];
  const candidates = Array.from({ length: 65 }, (_, i) => ({
    resume_id: `resume-${i}`, candidate_name: `Candidate ${String(i).padStart(3, '0')}`,
    email: `person${i}@example.com`, score: i, pass_fail: i >= 30,
    explanation: 'Match', injection_scan_passed: true, has_deep_analysis: false,
  }));
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith('/auth/session')) return route.fulfill({ json: {
      state: 'authenticated', csrf_token: 'test-csrf',
      user: { id: 'user-1', email: 'owner@example.com', verified: true },
      organization: { id: 'org-1', name: 'Example', role: 'owner', locked: false }, mfa_enabled: true,
    } });
    if (path.endsWith('/job-descriptions')) return route.fulfill({ json: { items: [job], total: 1 } });
    if (path.endsWith('/job-descriptions/job-1')) return route.fulfill({ json: job });
    if (path.endsWith('/unscored-resumes')) return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20, pages: 0 } });
    if (path.endsWith('/candidates')) {
      const params = url.searchParams;
      requests.push(params);
      const query = (params.get('q') ?? '').toLowerCase();
      const status = params.get('status');
      const key = (params.get('sort_by') ?? 'score') as 'score' | 'candidate_name' | 'pass_fail';
      const direction = params.get('sort_direction') === 'asc' ? 1 : -1;
      const filtered = candidates.filter((item) =>
        (item.candidate_name.toLowerCase().includes(query) || item.email.includes(query)) &&
        (status === 'pass' ? item.pass_fail : status === 'fail' ? !item.pass_fail : true)
      ).sort((a, b) => (a[key] < b[key] ? -1 : a[key] > b[key] ? 1 : 0) * direction);
      const current = Number(params.get('page') ?? 1);
      const size = Number(params.get('page_size') ?? 20);
      return route.fulfill({ json: {
        items: filtered.slice((current - 1) * size, current * size), total: filtered.length,
        page: current, page_size: size, pages: Math.ceil(filtered.length / size),
      } });
    }
    return route.fulfill({ status: 404, json: { detail: 'Unexpected API request' } });
  });
  return requests;
}

for (const path of ['/', '/jobs/job-1']) {
  test(`pagination, global search and sorting on ${path}`, async ({ page }) => {
    const requests = await mockCandidates(page);
    await page.goto(path);
    if (path === '/') {
      await page.getByRole('combobox').click();
      await page.getByRole('option', { name: 'Engineer — Example' }).click();
    }
    await expect(page.getByText('65 candidates · Page 1 of 4')).toBeVisible();
    for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(page.getByText('Candidate 000', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
    await page.getByRole('textbox', { name: 'Search candidates' }).fill('person1@example.com');
    await expect(page.getByText('1 candidates · Page 1 of 1')).toBeVisible();
    await expect(page.getByText('Candidate 001', { exact: true })).toBeVisible();
    expect(requests.at(-1)?.get('q')).toBe('person1@example.com');
    await page.getByRole('textbox', { name: 'Search candidates' }).fill('');
    await page.getByRole('combobox', { name: 'Candidate status' }).click();
    await page.getByRole('option', { name: 'Fail only' }).click();
    await expect(page.getByText('30 candidates · Page 1 of 2')).toBeVisible();
    await page.getByRole('button', { name: 'Name', exact: true }).click();
    await expect.poll(() => requests.at(-1)?.get('sort_by')).toBe('candidate_name');
    await page.getByRole('button', { name: 'Name', exact: true }).click();
    await expect.poll(() => requests.at(-1)?.get('sort_direction')).toBe('asc');
    await expect(page.getByRole('row').nth(1)).toContainText('Candidate 000');
  });
}


for (const path of ['/?jd=job-1', '/jobs/job-1']) {
  test(`recover uploads after refresh and retry scoring on ${path}`, async ({ page }) => {
    await mockCandidates(page);
    let uploaded = false;
    let scored = false;
    let attempts = 0;
    const resume = { id: 'recovered-id', filename: 'recover.pdf', candidate_name: null,
      email: null, injection_scan_passed: true, created_at: null };
    await page.route('**/api/v1/dashboard/jobs/job-1/unscored-resumes?**', (route) =>
      route.fulfill({ json: { items: uploaded && !scored ? [resume] : [],
        total: uploaded && !scored ? 1 : 0, page: 1, page_size: 20, pages: uploaded && !scored ? 1 : 0 } }));
    await page.route('**/api/v1/resumes/batch-upload', (route) => {
      uploaded = true;
      return route.fulfill({ json: { resumes: [{ ...resume, file_type: 'pdf',
        injection_scan: { passed: true, suspicion_score: 0 } }], total: 1, succeeded: 1, failed: 0 } });
    });
    await page.route('**/api/v1/analysis/fast-track', (route) => {
      expect(route.request().postDataJSON()).toEqual({ job_description_id: 'job-1', resume_ids: ['recovered-id'] });
      attempts += 1;
      scored = attempts > 1;
      return route.fulfill({ json: { job_description_id: 'job-1', total: 1,
        succeeded: scored ? 1 : 0, failed: scored ? 0 : 1,
        results: [{ resume_id: 'recovered-id', error: scored ? null : 'Analysis failed. Please try again.' }] } });
    });
    await page.goto(path);
    await page.locator('input[type=file]').last().setInputFiles({ name: 'recover.pdf', mimeType: 'application/pdf', buffer: Buffer.from('resume') });
    await expect(page.getByRole('checkbox', { name: 'recover.pdf', exact: true })).toBeVisible();
    await page.reload();
    await page.getByRole('checkbox', { name: 'recover.pdf', exact: true }).check();
    await page.getByRole('button', { name: 'Analyze selected (1)', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Analysis failed');
    await expect(page.getByRole('checkbox', { name: 'recover.pdf', exact: true })).toBeChecked();
    await page.getByRole('button', { name: 'Analyze selected (1)', exact: true }).click();
    await expect(page.getByText('No unscored resumes for this job.')).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'recover.pdf', exact: true })).toHaveCount(0);
    expect(attempts).toBe(2);
  });
}

for (const path of ['/?jd=job-1', '/jobs/job-1']) {
  for (const allFailed of [false, true]) {
    test(`show individual upload failures on ${path} (all failed: ${allFailed})`, async ({ page }) => {
      await mockCandidates(page);
      let uploaded = false;
      const resume = { id: 'good-id', filename: 'good.pdf', candidate_name: null,
        email: null, injection_scan_passed: true, created_at: null };
      await page.route('**/api/v1/dashboard/jobs/job-1/unscored-resumes?**', (route) =>
        route.fulfill({ json: { items: uploaded && !allFailed ? [resume] : [],
          total: uploaded && !allFailed ? 1 : 0, page: 1, page_size: 20, pages: uploaded && !allFailed ? 1 : 0 } }));
      await page.route('**/api/v1/resumes/batch-upload', (route) => {
        uploaded = true;
        const errors = [{ index: 1, filename: 'bad.pdf', error: 'Could not parse the uploaded document.' }];
        if (allFailed) errors.unshift({ index: 0, filename: 'good.pdf', error: 'Could not parse the uploaded document.' });
        return route.fulfill({ json: { resumes: allFailed ? [] : [{ ...resume, file_type: 'pdf',
          injection_scan: { passed: true, suspicion_score: 0 } }], total: 2,
          succeeded: allFailed ? 0 : 1, failed: allFailed ? 2 : 1, errors } });
      });
      await page.goto(path);
      await page.locator('input[type=file]').last().setInputFiles([
        { name: 'good.pdf', mimeType: 'application/pdf', buffer: Buffer.from('good') },
        { name: 'bad.pdf', mimeType: 'application/pdf', buffer: Buffer.from('bad') },
      ]);
      await expect(page.getByText(`${allFailed ? 0 : 1} succeeded`, { exact: true })).toBeVisible();
      await expect(page.getByText(`${allFailed ? 2 : 1} failed`, { exact: true })).toBeVisible();
      await expect(page.getByRole('alert').filter({ hasText: 'bad.pdf' })).toContainText('Could not parse');
      await expect(page.getByRole('checkbox', { name: 'bad.pdf', exact: true })).toHaveCount(0);
      if (allFailed) {
        await expect(page.getByRole('button', { name: 'Analyze selected (0)' })).toBeDisabled();
      } else {
        await page.getByRole('checkbox', { name: 'good.pdf', exact: true }).check();
        await expect(page.getByRole('button', { name: 'Analyze selected (1)' })).toBeEnabled();
      }
    });
  }
}
