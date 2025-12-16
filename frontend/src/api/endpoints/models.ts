import { apiClient } from '../client'
import type {
  CreateModelRequest,
  ModelResponse,
  ModelListItem,
  ModelTypeInfoResponse,
} from '../types'

export const modelsApi = {
  create: async (model: CreateModelRequest): Promise<ModelResponse> => {
    const response = await apiClient.post<ModelResponse>('/models/', model)
    return response.data
  },

  list: async (): Promise<ModelListItem[]> => {
    const response = await apiClient.get<ModelListItem[]>('/models/')
    return response.data
  },

  get: async (name: string): Promise<ModelResponse> => {
    const response = await apiClient.get<ModelResponse>(`/models/${name}`)
    return response.data
  },

  delete: async (name: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/models/${name}`)
    return response.data
  },

  listTypes: async (): Promise<ModelTypeInfoResponse[]> => {
    const response = await apiClient.get<ModelTypeInfoResponse[]>('/models/types/')
    return response.data
  },

  getType: async (name: string): Promise<ModelTypeInfoResponse> => {
    const response = await apiClient.get<ModelTypeInfoResponse>(`/models/types/${name}`)
    return response.data
  },

  getTypeSchema: async (name: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.get<Record<string, unknown>>(`/models/types/${name}/schema`)
    return response.data
  },
}
