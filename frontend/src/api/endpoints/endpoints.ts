import { apiClient } from '../client'
import type { EndpointListItem, CreateEndpointRequest, EndpointResponse } from '../types'

export const endpointsApi = {
  list: async (): Promise<EndpointListItem[]> => {
    const response = await apiClient.get<EndpointListItem[]>('/endpoints/')
    return response.data
  },

  create: async (request: CreateEndpointRequest): Promise<EndpointResponse> => {
    const response = await apiClient.post<EndpointResponse>('/endpoints/', request)
    return response.data
  },

  get: async (slug: string): Promise<EndpointResponse> => {
    const response = await apiClient.get<EndpointResponse>(`/endpoints/${slug}`)
    return response.data
  },

  delete: async (slug: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/endpoints/${slug}`)
    return response.data
  },
}
