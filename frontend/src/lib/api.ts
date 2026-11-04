let csrfToken: string | undefined;
let csrfRequest: Promise<void> | undefined;
let sessionRequest: Promise<unknown> | undefined;
let tokenGeneration = 0;
const expiryListeners = new Set<() => void>();

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function onSessionExpired(listener: () => void): () => void {
  expiryListeners.add(listener);
  return () => {
    expiryListeners.delete(listener);
  };
}

export function resetSessionToken(): void {
  tokenGeneration += 1;
  csrfToken = undefined;
  csrfRequest = undefined;
}

async function ensureCsrf(): Promise<void> {
  if (csrfToken) return;
  csrfRequest ??= fetchGet('/v1/auth/session')
    .then(() => undefined)
    .finally(() => {
      csrfRequest = undefined;
    });
  await csrfRequest;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const unsafe =
    options?.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method);
  const headers = new Headers(options?.headers);
  if (unsafe) {
    await ensureCsrf();
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  }
  const started = tokenGeneration;
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'same-origin',
    headers,
  });
  if (!response.ok) {
    const problem: unknown = await response.json().catch(() => null);
    const record =
      problem !== null && typeof problem === 'object'
        ? (problem as Record<string, unknown>)
        : {};
    const code =
      typeof record.title === 'string' ? record.title : 'request_failed';
    if (
      response.status === 401 &&
      (code === 'session_expired' ||
        code === 'authentication_required' ||
        !path.startsWith('/v1/auth/'))
    ) {
      resetSessionToken();
      expiryListeners.forEach((listener) => listener());
    }
    throw new ApiError(
      typeof record.detail === 'string'
        ? record.detail
        : `Request failed (${response.status})`,
      response.status,
      code
    );
  }
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json();
  if (
    body !== null &&
    typeof body === 'object' &&
    'csrf_token' in body &&
    typeof body.csrf_token === 'string'
  ) {
    if (unsafe || started === tokenGeneration) {
      if (unsafe) tokenGeneration += 1;
      csrfToken = body.csrf_token;
    }
  }
  return body as T;
}

export function fetchGet<T>(path: string): Promise<T> {
  if (path === '/v1/auth/session') {
    sessionRequest ??= request<T>(path).finally(() => {
      sessionRequest = undefined;
    });
    return sessionRequest as Promise<T>;
  }
  return request<T>(path);
}

export function fetchPost<T>(path: string, data?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
}

export function fetchDelete(path: string): Promise<void> {
  return request<void>(path, { method: 'DELETE' });
}

export function fetchPostMultipart<T>(
  path: string,
  data: FormData
): Promise<T> {
  return request<T>(path, { method: 'POST', body: data });
}
