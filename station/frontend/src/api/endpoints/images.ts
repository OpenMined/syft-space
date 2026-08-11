import { apiClient } from '@/api/client'
import type { ImageTagResponse } from '@/api/types'

export const imagesApi = {
  /** Admin. Newest syft-space image tags from the registry, for the version picker. */
  list: (limit = 5): Promise<ImageTagResponse[]> => apiClient.get(`/images?limit=${limit}`),
}
