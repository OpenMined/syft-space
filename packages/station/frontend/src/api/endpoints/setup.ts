import { apiClient } from '@/api/client'
import type { SetupResponse, UpdateSetupBody } from '@/api/types'

export const setupApi = {
  get: (): Promise<SetupResponse> => apiClient.get('/setup'),

  /** Admin only. Setting the domain is what marks setup done. */
  update: (body: UpdateSetupBody): Promise<SetupResponse> => apiClient.put('/setup', body),
}
