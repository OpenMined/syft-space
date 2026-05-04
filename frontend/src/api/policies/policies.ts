import { apiClient } from '../client'
import type { CreatePolicyRequest, PolicyResponse, PolicyListItem } from '../types'

export interface PolicyTypeInfo {
  name: string
  description: string
  config_schema: Record<string, unknown>
  icon: string
  enabled: boolean
}

export const policyTypesApi = {
  list: async (): Promise<PolicyTypeInfo[]> => {
    const response = await apiClient.get<PolicyTypeInfo[]>('/policies/types/')
    return response.data
  },

  get: async (name: string): Promise<PolicyTypeInfo> => {
    const response = await apiClient.get<PolicyTypeInfo>(`/policies/types/${name}`)
    return response.data
  },
}

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
