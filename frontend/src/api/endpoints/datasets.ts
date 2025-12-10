import { apiClient } from '../client'
import type { BrowseResponse, CreateDatasetRequest, DatasetResponse } from '../types'

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
}