import assert from 'node:assert/strict';
import { afterEach, mock, test } from 'node:test';
import { fetchGet, fetchPost, fetchPostMultipart } from '../src/lib/api.ts';

afterEach(() => mock.restoreAll());

test('GET uses the API proxy prefix and returns parsed JSON', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/analysis/deep/123');
    assert.equal(options, undefined);
    return Response.json({ status: 'completed' });
  });
  assert.deepEqual(await fetchGet('/v1/analysis/deep/123'), { status: 'completed' });
});

test('POST serializes JSON', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/analysis/deep');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.equal(options.body, JSON.stringify({ resume_id: '123' }));
    return Response.json({ analysis_id: '456' });
  });
  assert.deepEqual(await fetchPost('/v1/analysis/deep', { resume_id: '123' }), {
    analysis_id: '456',
  });
});

test('multipart POST preserves FormData and lets fetch set its boundary', async () => {
  const data = new FormData();
  data.append('files', new Blob(['resume']), 'resume.txt');
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/resumes/batch-upload');
    assert.equal(options.method, 'POST');
    assert.equal(options.body, data);
    assert.equal(options.headers, undefined);
    return Response.json({ uploaded: 1 });
  });
  assert.deepEqual(await fetchPostMultipart('/v1/resumes/batch-upload', data), { uploaded: 1 });
});

test('API errors expose backend detail', async () => {
  mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Not found' }, { status: 404 }));
  await assert.rejects(fetchGet('/v1/missing'), { message: 'Not found' });
});

test('non-JSON errors retain the HTTP status', async () => {
  mock.method(globalThis, 'fetch', async () => new Response('Bad gateway', { status: 502 }));
  await assert.rejects(fetchGet('/v1/missing'), { message: 'Request failed (502)' });
});
