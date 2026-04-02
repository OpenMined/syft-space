import { apiClient } from '../client'
import type {
  AnalyticsFilters,
  SummaryStatsResponse,
  TimeSeriesResponse,
  TopUsersResponse,
} from '../types/analytics'

export const analyticsApi = {
  getSummary: async (
    filters: AnalyticsFilters,
    signal?: AbortSignal,
  ): Promise<SummaryStatsResponse> => {
    const response = await apiClient.get<SummaryStatsResponse>('/analytics/summary', {
      params: filters,
      signal,
    })
    return response.data
  },

  getTimeSeries: async (
    filters: AnalyticsFilters,
    signal?: AbortSignal,
  ): Promise<TimeSeriesResponse> => {
    const response = await apiClient.get<TimeSeriesResponse>('/analytics/time-series', {
      params: filters,
      signal,
    })
    return response.data
  },

  getTopUsers: async (
    filters: AnalyticsFilters,
    signal?: AbortSignal,
  ): Promise<TopUsersResponse> => {
    const response = await apiClient.get<TopUsersResponse>('/analytics/top-users', {
      params: filters,
      signal,
    })
    return response.data
  },
}
