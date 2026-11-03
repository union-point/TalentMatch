async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);

  if (!response.ok) {
    const problem: unknown = await response.json().catch(() => null);
    const detail = problem !== null && typeof problem === 'object' && 'detail' in problem
      ? problem.detail
      : undefined;
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export function fetchGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function fetchPost<T>(path: string, data: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export function fetchPostMultipart<T>(path: string, data: FormData): Promise<T> {
  return request<T>(path, { method: 'POST', body: data });
}
