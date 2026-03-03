import { apiClient } from '../client'
import type { PublicUrlResponse, UpdatePublicUrlRequest, ProxyStatusResponse } from '../types'

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

  // Get proxy status
  getProxyStatus: async (): Promise<ProxyStatusResponse> => {
    const response = await apiClient.get('/settings/proxy')
    return response.data
  },

  // Configure proxy (fetches tunnel credentials from SyftHub automatically)
  configureProxy: async (): Promise<ProxyStatusResponse> => {
    const response = await apiClient.post('/settings/proxy')
    return response.data
  },

  // Disconnect proxy
  disconnectProxy: async (): Promise<ProxyStatusResponse> => {
    const response = await apiClient.delete('/settings/proxy')
    return response.data
  },
}
