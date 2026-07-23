import { apiClient } from '@/api/client'
import type { AdminUrlResponse, SpaceResponse, SpaceStatusResponse } from '@/api/types'

export const spacesApi = {
  /** Admin: all spaces on the station. */
  list: (): Promise<SpaceResponse[]> => apiClient.get('/spaces'),

  /** The signed-in member's spaces. */
  mine: (): Promise<SpaceResponse[]> => apiClient.get('/spaces/mine'),

  /** Live running/paused/unavailable status, read from Kubernetes. */
  status: (id: string): Promise<SpaceStatusResponse> => apiClient.get(`/spaces/${id}/status`),

  /** Free the space's compute; data is kept. */
  pause: (id: string): Promise<SpaceStatusResponse> => apiClient.post(`/spaces/${id}/pause`),

  resume: (id: string): Promise<SpaceStatusResponse> => apiClient.post(`/spaces/${id}/resume`),

  /** The space URL with the admin key attached — opens the space signed in. */
  adminUrl: (id: string): Promise<AdminUrlResponse> => apiClient.get(`/spaces/${id}/admin-url`),

  /** Replace the space admin API key (the space applies it on restart). */
  regenerateToken: (id: string): Promise<AdminUrlResponse> =>
    apiClient.post(`/spaces/${id}/token/regenerate`),
}
