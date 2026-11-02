import axios from 'axios'

/** The backend's user-facing reason from an error response, else the error's own message. */
export const apiErrorMessage = (error: unknown, fallback = 'Something went wrong'): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail.map((d) => (d && typeof d === 'object' ? d.msg : d)).filter(Boolean)
      if (messages.length > 0) return messages.join('; ')
    }
  }
  return error instanceof Error && error.message ? error.message : fallback
}
