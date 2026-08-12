/**
 * Minimal typed HTTP client for the station API.
 *
 * All requests go to the same origin under /api/v1 — the Vite dev server
 * proxies them to the backend (see vite.config.ts), and in production the
 * backend serves the built frontend itself. The session rides on an
 * HTTP-only cookie, so no auth headers are needed.
 */

const BASE_URL = '/api/v1'

/** A non-2xx response, with FastAPI's `detail` flattened to a message. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** FastAPI 422 validation errors come as a list of {loc, msg} objects. */
function detailToMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item.msg === 'string' ? item.msg : null))
      .filter((m): m is string => m !== null)
    if (messages.length > 0) return messages.join('; ')
  }
  return 'Request failed'
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    let detail: unknown
    try {
      detail = (await response.json()).detail
    } catch {
      detail = response.statusText
    }
    throw new ApiError(response.status, detailToMessage(detail))
  }
  return response.json() as Promise<T>
}

export const apiClient = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
}
