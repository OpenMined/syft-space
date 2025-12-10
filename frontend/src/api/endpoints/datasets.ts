import { apiClient } from '../client'
import type { BrowseResponse, CreateDatasetRequest, DatasetResponse, DatasetListItem, UpdateDatasetRequest } from '../types'

export const datasetsApi = {
  browse: async (path = '~', showHidden = false): Promise<BrowseResponse> => {
    const response = await apiClient.get<BrowseResponse>('/datasets/browse', {
      params: {
        path,
        show_hidden: showHidden,
      },
    })
    return response.data
  },

  create: async (dataset: CreateDatasetRequest): Promise<DatasetResponse> => {
    const response = await apiClient.post<DatasetResponse>('/datasets/', dataset)
    return response.data
  },

  list: async (): Promise<DatasetListItem[]> => {
    const response = await apiClient.get<DatasetListItem[]>('/datasets/')
    return response.data
  },

  delete: async (name: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/datasets/${name}`)
    return response.data
  },

  get: async (name: string): Promise<DatasetResponse> => {
    const response = await apiClient.get<DatasetResponse>(`/datasets/${name}`)
    return response.data
  },

  update: async (_name: string, _dataset: UpdateDatasetRequest): Promise<DatasetResponse> => {
    // TODO: Replace with actual PUT endpoint when backend implements it
    // For now, return a mock response to prevent errors
    console.warn('Update endpoint not yet implemented in backend')
    return Promise.reject(new Error('Update functionality not yet available'))
  },
}