import { apiClient } from '../client'
import type {
  IngestionStatusResponse,
  IngestionJobListResponse,
  StartIngestionResponse,
  StopIngestionResponse,
  RetryIngestionResponse,
} from '../types'

export const ingestionApi = {
  getStatus: async (datasetId: string): Promise<IngestionStatusResponse> => {
    const response = await apiClient.get<IngestionStatusResponse>(
      `/ingestion/datasets/${datasetId}/status`,
    )
    return response.data
  },

  listJobs: async (
    datasetId: string,
    status?: string,
    limit = 100,
    offset = 0,
  ): Promise<IngestionJobListResponse> => {
    const params: Record<string, unknown> = { limit, offset }
    if (status) params.status = status

    const response = await apiClient.get<IngestionJobListResponse>(
      `/ingestion/datasets/${datasetId}/jobs`,
      { params },
    )
    return response.data
  },

  start: async (datasetId: string): Promise<StartIngestionResponse> => {
    const response = await apiClient.post<StartIngestionResponse>(
      `/ingestion/datasets/${datasetId}/start`,
    )
    return response.data
  },

  stop: async (datasetId: string): Promise<StopIngestionResponse> => {
    const response = await apiClient.post<StopIngestionResponse>(
      `/ingestion/datasets/${datasetId}/stop`,
    )
    return response.data
  },

  retry: async (datasetId: string): Promise<RetryIngestionResponse> => {
    const response = await apiClient.post<RetryIngestionResponse>(
      `/ingestion/datasets/${datasetId}/retry`,
    )
    return response.data
  },
}
