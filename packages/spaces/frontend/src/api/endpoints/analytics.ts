import { apiClient } from '../client'
import type {
  AnalyticsFilters,
  SummaryStatsResponse,
  TimeSeriesResponse,
  TopUsersResponse,
  WordCloudResponse,
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

  getWordCloud: async (
    filters: AnalyticsFilters,
    ngramSize: number = 1,
    signal?: AbortSignal,
  ): Promise<WordCloudResponse> => {
    const response = await apiClient.get<WordCloudResponse>('/analytics/word-cloud', {
      params: { ...filters, ngram_size: ngramSize, max_words: 10 },
      signal,
    })
    return response.data
  },
}
