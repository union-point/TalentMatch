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
