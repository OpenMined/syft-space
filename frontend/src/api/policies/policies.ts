import { apiClient } from '../client'
import type { CreatePolicyRequest, PolicyResponse, PolicyListItem } from '../types'

export const policiesApi = {
  create: async (request: CreatePolicyRequest): Promise<PolicyResponse> => {
    const response = await apiClient.post<PolicyResponse>('/policies/', request)
    return response.data
  },

  list: async (): Promise<PolicyListItem[]> => {
    const response = await apiClient.get<PolicyListItem[]>('/policies/')
    return response.data
  },

  get: async (policyId: string): Promise<PolicyResponse> => {
    const response = await apiClient.get<PolicyResponse>(`/policies/${policyId}`)
    return response.data
  },

  delete: async (policyId: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/policies/${policyId}`)
    return response.data
  },
}