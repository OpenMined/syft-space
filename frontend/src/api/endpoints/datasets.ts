import { apiClient } from '../client'
import type {
  CreateDatasetRequest,
  DatasetResponse,
  DatasetListItem,
  SourceBrowseRequest,
  SelectionItemRequest,
  SelectionResponse,
  SelectionPageResponse,
  SelectionIdsResponse,
  SourceBrowseResponse,
  UpdateDatasetRequest,
  HealthcheckResponse,
  DatasetTypeInfoResponse,
} from '../types'

export const datasetsApi = {
  browse: async (
    dtype: string,
    parentId: string | null = null,
    configuration: Record<string, unknown> = {},
    cursor: string | null = null,
  ): Promise<SourceBrowseResponse> => {
    const body: SourceBrowseRequest = {
      dtype,
      configuration,
      parent_id: parentId,
      cursor,
    }
    const response = await apiClient.post<SourceBrowseResponse>('/datasets/browse', body)
    return response.data
  },

  // Browse an existing dataset's source using its stored credentials (server-side).
  // Used by the "add source" picker so credentials never round-trip to the client.
  browseDataset: async (
    name: string,
    parentId: string | null = null,
    cursor: string | null = null,
  ): Promise<SourceBrowseResponse> => {
    const response = await apiClient.post<SourceBrowseResponse>(`/datasets/${name}/browse`, {
      parent_id: parentId,
      cursor,
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

  update: async (name: string, dataset: UpdateDatasetRequest): Promise<DatasetResponse> => {
    const response = await apiClient.patch<DatasetResponse>(`/datasets/${name}`, dataset)
    return response.data
  },

  // A page of a dataset's selection picks. The selection is no longer inlined
  // in the dataset/endpoint payload — detail views fetch and page it here.
  getSelection: async (name: string, limit = 50, offset = 0): Promise<SelectionPageResponse> => {
    const response = await apiClient.get<SelectionPageResponse>(`/datasets/${name}/selection`, {
      params: { limit, offset },
    })
    return response.data
  },

  // Every selected item id for a dataset (unpaged) — for picker pre-selection.
  getSelectionIds: async (name: string): Promise<SelectionIdsResponse> => {
    const response = await apiClient.get<SelectionIdsResponse>(`/datasets/${name}/selection/ids`)
    return response.data
  },

  // Additively add picker items to a dataset's selection (source-agnostic).
  addSelection: async (name: string, items: SelectionItemRequest[]): Promise<SelectionResponse> => {
    const response = await apiClient.post<SelectionResponse>(`/datasets/${name}/selection`, {
      items,
    })
    return response.data
  },

  healthcheck: async (name: string): Promise<HealthcheckResponse> => {
    const response = await apiClient.get<HealthcheckResponse>(`/datasets/${name}/health`)
    return response.data
  },

  listTypes: async (): Promise<DatasetTypeInfoResponse[]> => {
    const response = await apiClient.get<DatasetTypeInfoResponse[]>('/datasets/types/')
    return response.data
  },

  getType: async (name: string): Promise<DatasetTypeInfoResponse> => {
    const response = await apiClient.get<DatasetTypeInfoResponse>(`/datasets/types/${name}`)
    return response.data
  },
}
