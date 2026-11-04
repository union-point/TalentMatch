import assert from 'node:assert/strict';
import { afterEach, mock, test } from 'node:test';
import {
  ApiError,
  fetchDelete,
  fetchGet,
  fetchPost,
  fetchPostMultipart,
  onSessionExpired,
  resetSessionToken,
} from '../src/lib/api.ts';

const anonymous = {
  state: 'anonymous',
  csrf_token: 'csrf-test-token',
  user: null,
  organization: null,
  mfa_enabled: false,
};

afterEach(() => {
  mock.restoreAll();
  resetSessionToken();
});

test('GET uses same-origin credentials and the API proxy prefix', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/analysis/deep/123');
    assert.equal(options.credentials, 'same-origin');
    return Response.json({ status: 'completed' });
  });
  assert.deepEqual(await fetchGet('/v1/analysis/deep/123'), {
    status: 'completed',
  });
});

test('POST bootstraps CSRF and serializes JSON', async () => {
  const calls = [];
  mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push(url);
    if (url === '/api/v1/auth/session') return Response.json(anonymous);
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.get('Content-Type'), 'application/json');
    assert.equal(options.headers.get('X-CSRF-Token'), anonymous.csrf_token);
    assert.equal(options.body, JSON.stringify({ resume_id: '123' }));
    return Response.json({ analysis_id: '456' });
  });
  assert.deepEqual(await fetchPost('/v1/analysis/deep', { resume_id: '123' }), {
    analysis_id: '456',
  });
  assert.deepEqual(calls, ['/api/v1/auth/session', '/api/v1/analysis/deep']);
});

test('multipart POST sends CSRF without replacing its boundary', async () => {
  const data = new FormData();
  data.append('files', new Blob(['resume']), 'resume.txt');
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url === '/api/v1/auth/session') return Response.json(anonymous);
    assert.equal(options.method, 'POST');
    assert.equal(options.body, data);
    assert.equal(options.headers.get('Content-Type'), null);
    assert.equal(options.headers.get('X-CSRF-Token'), anonymous.csrf_token);
    return Response.json({ uploaded: 1 });
  });
  assert.deepEqual(await fetchPostMultipart('/v1/resumes/batch-upload', data), {
    uploaded: 1,
  });
});

test('DELETE supports empty responses', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url === '/api/v1/auth/session') return Response.json(anonymous);
    assert.equal(options.method, 'DELETE');
    assert.equal(options.headers.get('X-CSRF-Token'), anonymous.csrf_token);
    return new Response(null, { status: 204 });
  });
  assert.equal(await fetchDelete('/v1/organization/members/123'), undefined);
});

test('API errors expose backend detail, status, and machine-readable code', async () => {
  mock.method(globalThis, 'fetch', async () =>
    Response.json({ title: 'not_found', detail: 'Not found' }, { status: 404 })
  );
  await assert.rejects(
    fetchGet('/v1/missing'),
    (error) =>
      error instanceof ApiError &&
      error.status === 404 &&
      error.code === 'not_found' &&
      error.message === 'Not found'
  );
});

test('non-JSON errors retain the HTTP status', async () => {
  mock.method(
    globalThis,
    'fetch',
    async () => new Response('Bad gateway', { status: 502 })
  );
  await assert.rejects(fetchGet('/v1/missing'), {
    message: 'Request failed (502)',
  });
});

test('session expiry notifies the provider and resets CSRF', async () => {
  let expired = 0;
  const unsubscribe = onSessionExpired(() => {
    expired += 1;
  });
  mock.method(globalThis, 'fetch', async () =>
    Response.json({ title: 'session_expired' }, { status: 401 })
  );
  await assert.rejects(fetchGet('/v1/job-descriptions'));
  assert.equal(expired, 1);
  unsubscribe();
});

test('incorrect login credentials do not expire the anonymous session', async () => {
  let expired = false;
  const unsubscribe = onSessionExpired(() => {
    expired = true;
  });
  mock.method(globalThis, 'fetch', async (url) =>
    url.endsWith('/session')
      ? Response.json(anonymous)
      : Response.json(
          {
            title: 'invalid_credentials',
            detail: 'Email or password is incorrect.',
          },
          { status: 401 }
        )
  );
  await assert.rejects(
    fetchPost('/v1/auth/login', {
      email: 'person@example.com',
      password: 'bad',
    })
  );
  assert.equal(expired, false);
  unsubscribe();
});

test('session rotation replaces the CSRF token for subsequent requests', async () => {
  let mutations = 0;
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/session')) return Response.json(anonymous);
    mutations += 1;
    assert.equal(
      options.headers.get('X-CSRF-Token'),
      mutations === 1 ? anonymous.csrf_token : 'rotated'
    );
    return Response.json({ ...anonymous, csrf_token: 'rotated' });
  });
  await fetchPost('/v1/auth/login', {});
  await fetchPost('/v1/auth/logout', {});
});

test('concurrent mutations share the CSRF bootstrap', async () => {
  let bootstraps = 0;
  mock.method(globalThis, 'fetch', async (url) => {
    if (url.endsWith('/session')) {
      bootstraps += 1;
      return Response.json(anonymous);
    }
    return Response.json({ ok: true });
  });
  await Promise.all([fetchPost('/v1/one', {}), fetchPost('/v1/two', {})]);
  assert.equal(bootstraps, 1);
});

test('concurrent session reads share one bootstrap request', async () => {
  let bootstraps = 0;
  mock.method(globalThis, 'fetch', async () => {
    bootstraps += 1;
    return Response.json(anonymous);
  });
  await Promise.all([
    fetchGet('/v1/auth/session'),
    fetchGet('/v1/auth/session'),
  ]);
  assert.equal(bootstraps, 1);
});

test('a stale session response cannot replace a rotated CSRF token', async () => {
  let finishRead;
  let calls = 0;
  mock.method(globalThis, 'fetch', async (url, options) => {
    calls += 1;
    if (calls === 1) return Response.json(anonymous);
    if (calls === 2)
      return new Promise((resolve) => {
        finishRead = () => resolve(Response.json(anonymous));
      });
    if (calls === 3)
      return Response.json({ ...anonymous, csrf_token: 'new-token' });
    assert.equal(options.headers.get('X-CSRF-Token'), 'new-token');
    return Response.json({ ok: true });
  });
  await fetchGet('/v1/auth/session');
  const pending = fetchGet('/v1/auth/session');
  await fetchPost('/v1/auth/login', {});
  finishRead();
  await pending;
  await fetchPost('/v1/action', {});
});

test('logout abandons an old bootstrap and preserves the new session token', async () => {
  let completeOld;
  let reads = 0;
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/session')) {
      reads += 1;
      if (reads === 1)
        return new Promise((resolve) => {
          completeOld = () => resolve(Response.json(anonymous));
        });
      return Response.json({ ...anonymous, csrf_token: 'fresh-session' });
    }
    assert.equal(options.headers.get('X-CSRF-Token'), 'fresh-session');
    return Response.json({ ok: true });
  });
  const old = fetchGet('/v1/auth/session');
  resetSessionToken();
  await fetchPost('/v1/first', {});
  completeOld();
  await old;
  await fetchPost('/v1/second', {});
  assert.equal(reads, 2);
});
