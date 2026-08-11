import { apiClient } from '@/api/client'
import type { LoginBody, MeResponse } from '@/api/types'

export const authApi = {
  /** Sign in with SyftHub credentials; the session cookie is set by the response. */
  login: (body: LoginBody): Promise<MeResponse> => apiClient.post('/auth/login', body),

  logout: (): Promise<{ message: string }> => apiClient.post('/auth/logout'),

  /** Current session, for restore on reload (401 when signed out). */
  me: (): Promise<MeResponse> => apiClient.get('/auth/me'),
}
