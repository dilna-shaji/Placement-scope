/** Thin fetch wrapper: cookies for the session, CSRF header for writes, typed errors. */
export class ApiError extends Error {
  status: number;
  code?: string;
  fields: Record<string, string>;
  constructor(message: string, status: number, code?: string, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

let onUnauthenticated: (() => void) | null = null;
export const setUnauthenticatedHandler = (fn: () => void) => { onUnauthenticated = fn; };

const csrf = () => document.cookie.split('; ').find((c) => c.startsWith('ph_csrf='))?.split('=')[1] ?? '';

async function request<T>(method: string, url: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== 'GET') headers['X-CSRF-Token'] = csrf();
  if (body && !isForm) headers['Content-Type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(url, { method, headers, credentials: 'same-origin', body: isForm ? (body as FormData) : body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError('Cannot reach the PlacementHub server. Is the backend running?', 0);
  }
  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('json') ? await res.json().catch(() => ({})) : null;
  if (!res.ok) {
    if (res.status === 401 && data?.code === 'unauthenticated' && onUnauthenticated && !url.startsWith('/api/auth/')) onUnauthenticated();
    throw new ApiError(data?.error || `Request failed (${res.status})`, res.status, data?.code, data?.fields);
  }
  return (data ?? (res as unknown)) as T;
}

export const api = {
  get: <T,>(url: string) => request<T>('GET', url),
  post: <T,>(url: string, body?: unknown) => request<T>('POST', url, body ?? {}),
  put: <T,>(url: string, body?: unknown) => request<T>('PUT', url, body ?? {}),
  del: <T,>(url: string) => request<T>('DELETE', url),
  upload: <T,>(url: string, form: FormData) => request<T>('POST', url, form, true),
};

export const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : '';
};
