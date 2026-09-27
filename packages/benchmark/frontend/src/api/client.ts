// The same shape spaces/frontend uses for its own auth token (see its
// src/router/index.ts and src/api/client.ts): read once off the URL, keep
// in localStorage, attach as a bearer header from then on. The one
// difference is scope — this token names one target and expires; that
// difference lives entirely in control/session.py, not in this client.
const TOKEN_KEY = "benchmark_console_token";

export function bootstrapToken(): void {
  const url = new URL(window.location.href);
  const fromQuery = url.searchParams.get("token");
  if (!fromQuery) return;
  localStorage.setItem(TOKEN_KEY, fromQuery);
  url.searchParams.delete("token");
  window.history.replaceState({}, "", url.toString());
}

export function hasToken(): boolean {
  return Boolean(localStorage.getItem(TOKEN_KEY));
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY) ?? "";
  const response = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = (await response.json()) as { detail?: string };
      detail = data.detail ?? detail;
    } catch {
      // the body was not JSON — the status text is all there is to show
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string): Promise<T> => request<T>("GET", path),
  post: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("PATCH", path, body),
  delete: (path: string): Promise<void> => request<void>("DELETE", path),
};

export function query(
  params: Record<string, string | number | undefined>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
