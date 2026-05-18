import axios from 'axios'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import { analyticsApi } from '@/api/endpoints/analytics'
import type {
  AnalyticsFilters,
  SummaryStatsResponse,
  TimeRange,
  TimeSeriesResponse,
  TopUsersResponse,
  WordCloudResponse,
} from '@/api/types/analytics'

export const useAnalyticsStore = defineStore('analytics', () => {
  // ---- Filter state ----
  const timeRange = ref<TimeRange>('30d')
  const endpointId = ref<string | undefined>(undefined)
  const ngramSize = ref(1)

  // ---- Summary stats ----
  const summary = ref<SummaryStatsResponse | null>(null)
  const summaryLoading = ref(false)
  const summaryError = ref<string | null>(null)

  // ---- Time series ----
  const timeSeries = ref<TimeSeriesResponse | null>(null)
  const timeSeriesLoading = ref(false)
  const timeSeriesError = ref<string | null>(null)

  // ---- Top users ----
  const topUsers = ref<TopUsersResponse | null>(null)
  const topUsersLoading = ref(false)
  const topUsersError = ref<string | null>(null)

  // ---- Word cloud ----
  const wordCloud = ref<WordCloudResponse | null>(null)
  const wordCloudLoading = ref(false)
  const wordCloudError = ref<string | null>(null)

  // ---- Abort controllers for stale request cancellation ----
  let summaryAbort: AbortController | null = null
  let timeSeriesAbort: AbortController | null = null
  let topUsersAbort: AbortController | null = null
  let wordCloudAbort: AbortController | null = null

  // ---- Computed ----
  const filters = computed<AnalyticsFilters>(() => ({
    time_range: timeRange.value,
    endpoint_id: endpointId.value,
  }))

  const isLoading = computed(
    () =>
      summaryLoading.value ||
      timeSeriesLoading.value ||
      topUsersLoading.value ||
      wordCloudLoading.value,
  )

  const hasData = computed(
    () =>
      summary.value !== null ||
      timeSeries.value !== null ||
      topUsers.value !== null ||
      wordCloud.value !== null,
  )

  // ---- Fetch methods ----
  const fetchSummary = async () => {
    summaryAbort?.abort()
    summaryAbort = new AbortController()
    summaryLoading.value = true
    summaryError.value = null
    try {
      summary.value = await analyticsApi.getSummary(filters.value, summaryAbort.signal)
    } catch (err) {
      if (axios.isCancel(err)) return
      summaryError.value = err instanceof Error ? err.message : 'Failed to load summary'
    } finally {
      summaryLoading.value = false
    }
  }

  const fetchTimeSeries = async () => {
    timeSeriesAbort?.abort()
    timeSeriesAbort = new AbortController()
    timeSeriesLoading.value = true
    timeSeriesError.value = null
    try {
      timeSeries.value = await analyticsApi.getTimeSeries(filters.value, timeSeriesAbort.signal)
    } catch (err) {
      if (axios.isCancel(err)) return
      timeSeriesError.value = err instanceof Error ? err.message : 'Failed to load time series'
    } finally {
      timeSeriesLoading.value = false
    }
  }

  const fetchTopUsers = async () => {
    topUsersAbort?.abort()
    topUsersAbort = new AbortController()
    topUsersLoading.value = true
    topUsersError.value = null
    try {
      topUsers.value = await analyticsApi.getTopUsers(filters.value, topUsersAbort.signal)
    } catch (err) {
      if (axios.isCancel(err)) return
      topUsersError.value = err instanceof Error ? err.message : 'Failed to load top users'
    } finally {
      topUsersLoading.value = false
    }
  }

  const fetchWordCloud = async () => {
    wordCloudAbort?.abort()
    wordCloudAbort = new AbortController()
    wordCloudLoading.value = true
    wordCloudError.value = null
    try {
      wordCloud.value = await analyticsApi.getWordCloud(
        filters.value,
        ngramSize.value,
        wordCloudAbort.signal,
      )
    } catch (err) {
      if (axios.isCancel(err)) return
      wordCloudError.value = err instanceof Error ? err.message : 'Failed to load word cloud'
    } finally {
      wordCloudLoading.value = false
    }
  }

  const fetchAll = async () => {
    await Promise.all([fetchSummary(), fetchTimeSeries(), fetchTopUsers(), fetchWordCloud()])
  }

  // ---- Export ----
  const exportData = () => {
    if (!hasData.value) {
      toast.info('No data to export')
      return
    }
    const data = {
      exportedAt: new Date().toISOString(),
      filters: {
        timeRange: timeRange.value,
        endpointId: endpointId.value ?? 'all',
      },
      summary: summary.value,
      timeSeries: timeSeries.value,
      topUsers: topUsers.value,
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analytics-export-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('Analytics data exported')
  }

  return {
    // Filter state
    timeRange,
    endpointId,
    ngramSize,
    // Summary
    summary,
    summaryLoading,
    summaryError,
    // Time series
    timeSeries,
    timeSeriesLoading,
    timeSeriesError,
    // Top users
    topUsers,
    topUsersLoading,
    topUsersError,
    // Word cloud
    wordCloud,
    wordCloudLoading,
    wordCloudError,
    // Computed
    filters,
    isLoading,
    hasData,
    // Actions
    fetchSummary,
    fetchTimeSeries,
    fetchTopUsers,
    fetchWordCloud,
    fetchAll,
    exportData,
  }
})
