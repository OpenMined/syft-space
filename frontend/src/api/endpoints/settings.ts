import { apiClient } from '../client'
import type { PublicUrlResponse, UpdatePublicUrlRequest } from '../types'

export const settingsApi = {
  // Get current public URL
  getPublicUrl: async (): Promise<PublicUrlResponse> => {
    const response = await apiClient.get('/settings/public-url')
    return response.data
  },

  // Update public URL
  updatePublicUrl: async (data: UpdatePublicUrlRequest): Promise<PublicUrlResponse> => {
    const response = await apiClient.patch('/settings/public-url', data)
    return response.data
  },
}
