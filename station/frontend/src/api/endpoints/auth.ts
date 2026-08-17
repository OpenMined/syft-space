import { apiClient } from '@/api/client'
import type { AuthConfig, GoogleLoginBody, LoginBody, MeResponse } from '@/api/types'

export const authApi = {
  /** Which sign-in methods the page should offer (e.g. is Google configured). */
  config: (): Promise<AuthConfig> => apiClient.get('/auth/config'),

  /** Sign in with SyftHub credentials; the session cookie is set by the response. */
  login: (body: LoginBody): Promise<MeResponse> => apiClient.post('/auth/login', body),

  /** Sign in with a Google ID token (existing SyftHub users only). */
  loginWithGoogle: (body: GoogleLoginBody): Promise<MeResponse> =>
    apiClient.post('/auth/login/google', body),

  logout: (): Promise<{ message: string }> => apiClient.post('/auth/logout'),

  /** Current session, for restore on reload (401 when signed out). */
  me: (): Promise<MeResponse> => apiClient.get('/auth/me'),
}
