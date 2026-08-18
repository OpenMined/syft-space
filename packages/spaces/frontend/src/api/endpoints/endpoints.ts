import { apiClient } from '../client'
import type {
  EndpointListItem,
  CreateEndpointRequest,
  EndpointResponse,
  SlugAvailabilityRequest,
  SlugAvailabilityResponse,
  PublishEndpointRequest,
  PublishEndpointResponse,
  UnpublishResult,
  UpdateEndpointRequest,
  EndpointQueryRequest,
  EndpointQueryResponse,
} from '../types'

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

  update: async (slug: string, request: UpdateEndpointRequest): Promise<EndpointResponse> => {
    const response = await apiClient.patch<EndpointResponse>(`/endpoints/${slug}`, request)
    return response.data
  },

  validateSlug: async (request: SlugAvailabilityRequest): Promise<SlugAvailabilityResponse> => {
    const response = await apiClient.post<SlugAvailabilityResponse>(
      '/endpoints/validate-slug',
      request,
    )
    return response.data
  },

  publish: async (
    slug: string,
    request: PublishEndpointRequest,
  ): Promise<PublishEndpointResponse> => {
    const response = await apiClient.post<PublishEndpointResponse>(
      `/endpoints/${slug}/publish`,
      request,
    )
    return response.data
  },

  unpublish: async (slug: string): Promise<UnpublishResult[]> => {
    const response = await apiClient.delete<UnpublishResult[]>(`/endpoints/${slug}/unpublish`)
    return response.data
  },

  query: async (
    slug: string,
    request: EndpointQueryRequest,
    options?: { signal?: AbortSignal },
  ): Promise<EndpointQueryResponse> => {
    const response = await apiClient.post<EndpointQueryResponse>(
      `/endpoints/${slug}/preview`,
      request,
      { signal: options?.signal },
    )
    return response.data
  },
}
