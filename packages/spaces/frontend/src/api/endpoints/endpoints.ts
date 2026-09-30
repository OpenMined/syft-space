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
  EndpointQualityResponse,
  PublishQualityCardResponse,
  QualityHistoryResponse,
  RetractQualityResponse,
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

  /**
   * The benchmark card stored for this endpoint.
   *
   * Always available to the owner, whatever the benchmarks setting says: he
   * must be able to read what is said in his name even after closing the door
   * on new reports.
   */
  getQuality: async (slug: string): Promise<EndpointQualityResponse> => {
    const response = await apiClient.get<EndpointQualityResponse>(
      `/endpoints/${slug}/quality`,
    )
    return response.data
  },

  /**
   * Withdraw the published card, here and at every marketplace showing it.
   *
   * Idempotent: an endpoint with no card comes back `cleared: false`, which is
   * not an error.
   */
  retractQuality: async (slug: string): Promise<RetractQualityResponse> => {
    const response = await apiClient.delete<RetractQualityResponse>(
      `/endpoints/${slug}/quality`,
    )
    return response.data
  },

  /**
   * Every card this endpoint has collected, newest run first.
   *
   * Withdrawn runs are in it: a share is only readable next to the shares
   * before it, and a history with the awkward runs left out is not one.
   */
  getQualityHistory: async (slug: string): Promise<QualityHistoryResponse> => {
    const response = await apiClient.get<QualityHistoryResponse>(
      `/endpoints/${slug}/quality/history`,
    )
    return response.data
  },

  /**
   * Put an earlier run back on top of a later one.
   *
   * A newer run is not automatically the truer one — it can rest on a question
   * set that turned out to be wrong. Nothing is deleted: the runs measured
   * after the chosen one are marked withdrawn, so the move is reversible by
   * choosing the newer one again.
   */
  publishQualityCard: async (slug: string, cardId: string): Promise<PublishQualityCardResponse> => {
    const response = await apiClient.post<PublishQualityCardResponse>(
      `/endpoints/${slug}/quality/cards/${cardId}/publish`,
    )
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
