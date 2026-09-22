/**
 * API error message extraction.
 */

/**
 * Pull `detail` off an axios error the way this backend's FastAPI error
 * envelope shapes it (`{ detail: "..." }`), falling back to `Error.message`
 * and then to a caller-supplied default.
 */
export function apiErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  return error instanceof Error ? error.message : fallback
}
