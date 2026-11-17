/** The FastAPI `detail` of an axios error, else `Error.message`, else `fallback`. */
export function apiErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  // Validation errors: a list of `{ msg }`.
  if (Array.isArray(detail)) {
    const lines = detail
      .map((item) => (typeof item === 'string' ? item : (item as { msg?: unknown })?.msg))
      .filter((msg): msg is string => typeof msg === 'string' && !!msg)
    if (lines.length) return lines.join(' ')
  }
  return error instanceof Error ? error.message : fallback
}
