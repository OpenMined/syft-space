import { apiClient } from '../client'
import type { EndpointListItem } from '../types'

export const endpointsApi = {
  list: async (): Promise<EndpointListItem[]> => {
    const response = await apiClient.get<EndpointListItem[]>('/endpoints/')
    return response.data
  },
}
