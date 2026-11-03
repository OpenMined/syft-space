import axios from 'axios'

/** The backend's `detail` as one string, or undefined when the response has none. */
export const apiErrorDetail = (error: unknown): string | undefined => {
  if (!axios.isAxiosError(error)) return undefined
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((d) => (d && typeof d === 'object' ? d.msg : d)).filter(Boolean)
    if (messages.length > 0) return messages.join('; ')
  }
  return undefined
}

/** `apiErrorDetail`, else the error's own message, else `fallback`. */
export const apiErrorMessage = (error: unknown, fallback = 'Something went wrong'): string =>
  apiErrorDetail(error) ?? (error instanceof Error && error.message ? error.message : fallback)
