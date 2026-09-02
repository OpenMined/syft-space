import { apiClient } from '@/api/client'
import type {
  ConnectIdentityBody,
  IdentityResponse,
  SetupResponse,
  UpdateSetupBody,
} from '@/api/types'

export const setupApi = {
  get: (): Promise<SetupResponse> => apiClient.get('/setup'),

  /** Admin only. Setting the domain is what marks setup done. */
  update: (body: UpdateSetupBody): Promise<SetupResponse> => apiClient.put('/setup', body),

  /** Admin only. The station's SyftHub identity — never the token itself. */
  identity: (): Promise<IdentityResponse> => apiClient.get('/setup/identity'),

  /** Admin only. Connect or rotate it; registers the station's satellite. */
  connectIdentity: (body: ConnectIdentityBody): Promise<IdentityResponse> =>
    apiClient.put('/setup/identity', body),
}
