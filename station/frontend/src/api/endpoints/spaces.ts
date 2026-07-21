import { apiClient } from '@/api/client'
import type {
  SpaceResponse,
  SpaceStatusResponse,
  TokenRevealResponse,
  TokenStatusResponse,
} from '@/api/types'

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

  tokenStatus: (id: string): Promise<TokenStatusResponse> => apiClient.get(`/spaces/${id}/token`),

  /** One-time reveal of the space admin API key (410 once already revealed). */
  revealToken: (id: string): Promise<TokenRevealResponse> =>
    apiClient.post(`/spaces/${id}/token/reveal`),

  /** Replace the space admin API key with a fresh unrevealed one. */
  regenerateToken: (id: string): Promise<TokenStatusResponse> =>
    apiClient.post(`/spaces/${id}/token/regenerate`),
}
