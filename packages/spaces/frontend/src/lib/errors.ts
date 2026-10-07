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
  // A validation refusal: a list of `{ msg }`, one per field.
  if (Array.isArray(detail)) {
    const lines = detail
      .map((item) => (typeof item === 'string' ? item : (item as { msg?: unknown })?.msg))
      .filter((msg): msg is string => typeof msg === 'string' && !!msg)
    if (lines.length) return lines.join(' ')
  }
  return error instanceof Error ? error.message : fallback
}
