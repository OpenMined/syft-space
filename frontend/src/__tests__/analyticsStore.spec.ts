import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAnalyticsStore } from '@/stores/analytics'
import type {
  SummaryStatsResponse,
  TimeSeriesResponse,
  TopUsersResponse,
  WordCloudResponse,
} from '@/api/types/analytics'

// Mock the analytics API module
vi.mock('@/api/endpoints/analytics', () => ({
  analyticsApi: {
    getSummary: vi.fn(),
    getTimeSeries: vi.fn(),
    getTopUsers: vi.fn(),
    getWordCloud: vi.fn(),
  },
}))

// Import the mocked module so we can control return values
import { analyticsApi } from '@/api/endpoints/analytics'

const mockSummary: SummaryStatsResponse = {
  active_endpoints: { value: 5, change_value: 2, change_label: '+2 this period' },
  total_queries: { value: 100, change_value: 25, change_label: '+25% from last period' },
  total_revenue: { value: 50.0, change_value: 200, change_label: '$200.00 this month' },
  active_users: { value: 10, change_value: 0, change_label: '30d' },
}

const mockTimeSeries: TimeSeriesResponse = {
  query_volume: [
    { label: 'Jan 1', value: 10 },
    { label: 'Jan 2', value: 20 },
  ],
  user_activity: [
    { label: 'Jan 1', value: 3 },
    { label: 'Jan 2', value: 5 },
  ],
  revenue: [
    { label: 'Jan 1', value: 5.0 },
    { label: 'Jan 2', value: 10.0 },
  ],
}

const mockTopUsers: TopUsersResponse = {
  users: [
    { user_email: 'alice@test.com', query_count: 50, revenue: 100.0 },
    { user_email: 'bob@test.com', query_count: 30, revenue: 50.0 },
  ],
}

const mockWordCloud: WordCloudResponse = {
  words: [
    { word: 'learning', count: 15 },
    { word: 'machine', count: 12 },
    { word: 'model', count: 8 },
  ],
}

describe('useAnalyticsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ============== Initial state ==============

  it('has correct initial state', () => {
    const store = useAnalyticsStore()

    expect(store.timeRange).toBe('30d')
    expect(store.endpointId).toBeUndefined()
    expect(store.summary).toBeNull()
    expect(store.summaryLoading).toBe(false)
    expect(store.summaryError).toBeNull()
    expect(store.timeSeries).toBeNull()
    expect(store.topUsers).toBeNull()
    expect(store.isLoading).toBe(false)
    expect(store.hasData).toBe(false)
  })

  // ============== fetchSummary ==============

  describe('fetchSummary', () => {
    it('fetches and stores summary data', async () => {
      vi.mocked(analyticsApi.getSummary).mockResolvedValue(mockSummary)
      const store = useAnalyticsStore()

      await store.fetchSummary()

      expect(store.summary).toEqual(mockSummary)
      expect(store.summaryLoading).toBe(false)
      expect(store.summaryError).toBeNull()
      expect(store.hasData).toBe(true)
    })

    it('sets loading state during fetch', async () => {
      let resolvePromise: (v: SummaryStatsResponse) => void
      vi.mocked(analyticsApi.getSummary).mockReturnValue(
        new Promise((r) => {
          resolvePromise = r
        }),
      )

      const store = useAnalyticsStore()
      const promise = store.fetchSummary()

      expect(store.summaryLoading).toBe(true)

      resolvePromise!(mockSummary)
      await promise

      expect(store.summaryLoading).toBe(false)
    })

    it('handles errors', async () => {
      vi.mocked(analyticsApi.getSummary).mockRejectedValue(new Error('Network fail'))
      const store = useAnalyticsStore()

      await store.fetchSummary()

      expect(store.summaryError).toBe('Network fail')
      expect(store.summaryLoading).toBe(false)
      expect(store.summary).toBeNull()
    })

    it('passes current filters to API', async () => {
      vi.mocked(analyticsApi.getSummary).mockResolvedValue(mockSummary)
      const store = useAnalyticsStore()
      store.timeRange = '7d'
      store.endpointId = 'ep-123'

      await store.fetchSummary()

      expect(analyticsApi.getSummary).toHaveBeenCalledWith(
        { time_range: '7d', endpoint_id: 'ep-123' },
        expect.any(AbortSignal),
      )
    })
  })

  // ============== fetchTimeSeries ==============

  describe('fetchTimeSeries', () => {
    it('fetches and stores time series data', async () => {
      vi.mocked(analyticsApi.getTimeSeries).mockResolvedValue(mockTimeSeries)
      const store = useAnalyticsStore()

      await store.fetchTimeSeries()

      expect(store.timeSeries).toEqual(mockTimeSeries)
      expect(store.timeSeriesLoading).toBe(false)
    })

    it('handles errors', async () => {
      vi.mocked(analyticsApi.getTimeSeries).mockRejectedValue(new Error('Timeout'))
      const store = useAnalyticsStore()

      await store.fetchTimeSeries()

      expect(store.timeSeriesError).toBe('Timeout')
      expect(store.timeSeries).toBeNull()
    })
  })

  // ============== fetchTopUsers ==============

  describe('fetchTopUsers', () => {
    it('fetches and stores top users data', async () => {
      vi.mocked(analyticsApi.getTopUsers).mockResolvedValue(mockTopUsers)
      const store = useAnalyticsStore()

      await store.fetchTopUsers()

      expect(store.topUsers).toEqual(mockTopUsers)
      expect(store.topUsersLoading).toBe(false)
    })

    it('handles errors', async () => {
      vi.mocked(analyticsApi.getTopUsers).mockRejectedValue(new Error('500'))
      const store = useAnalyticsStore()

      await store.fetchTopUsers()

      expect(store.topUsersError).toBe('500')
    })
  })

  // ============== fetchWordCloud ==============

  describe('fetchWordCloud', () => {
    it('fetches and stores word cloud data', async () => {
      vi.mocked(analyticsApi.getWordCloud).mockResolvedValue(mockWordCloud)
      const store = useAnalyticsStore()

      await store.fetchWordCloud()

      expect(store.wordCloud).toEqual(mockWordCloud)
      expect(store.wordCloudLoading).toBe(false)
    })

    it('handles errors', async () => {
      vi.mocked(analyticsApi.getWordCloud).mockRejectedValue(new Error('NLP fail'))
      const store = useAnalyticsStore()

      await store.fetchWordCloud()

      expect(store.wordCloudError).toBe('NLP fail')
      expect(store.wordCloud).toBeNull()
    })
  })

  // ============== fetchAll ==============

  describe('fetchAll', () => {
    it('fetches all four datasets in parallel', async () => {
      vi.mocked(analyticsApi.getSummary).mockResolvedValue(mockSummary)
      vi.mocked(analyticsApi.getTimeSeries).mockResolvedValue(mockTimeSeries)
      vi.mocked(analyticsApi.getTopUsers).mockResolvedValue(mockTopUsers)
      vi.mocked(analyticsApi.getWordCloud).mockResolvedValue(mockWordCloud)

      const store = useAnalyticsStore()
      await store.fetchAll()

      expect(store.summary).toEqual(mockSummary)
      expect(store.timeSeries).toEqual(mockTimeSeries)
      expect(store.topUsers).toEqual(mockTopUsers)
      expect(store.wordCloud).toEqual(mockWordCloud)
    })

    it('partial failure does not block other fetches', async () => {
      vi.mocked(analyticsApi.getSummary).mockRejectedValue(new Error('fail'))
      vi.mocked(analyticsApi.getTimeSeries).mockResolvedValue(mockTimeSeries)
      vi.mocked(analyticsApi.getTopUsers).mockResolvedValue(mockTopUsers)
      vi.mocked(analyticsApi.getWordCloud).mockResolvedValue(mockWordCloud)

      const store = useAnalyticsStore()
      await store.fetchAll()

      expect(store.summaryError).toBe('fail')
      expect(store.timeSeries).toEqual(mockTimeSeries)
      expect(store.topUsers).toEqual(mockTopUsers)
    })
  })

  // ============== filters computed ==============

  describe('filters', () => {
    it('reflects current filter state', () => {
      const store = useAnalyticsStore()

      expect(store.filters).toEqual({
        time_range: '30d',
        endpoint_id: undefined,
      })

      store.timeRange = '90d'
      store.endpointId = 'ep-1'

      expect(store.filters).toEqual({
        time_range: '90d',
        endpoint_id: 'ep-1',
      })
    })
  })

  // ============== isLoading ==============

  describe('isLoading', () => {
    it('is true when any fetch is loading', async () => {
      let resolvePromise: (v: SummaryStatsResponse) => void
      vi.mocked(analyticsApi.getSummary).mockReturnValue(
        new Promise((r) => {
          resolvePromise = r
        }),
      )
      vi.mocked(analyticsApi.getTimeSeries).mockResolvedValue(mockTimeSeries)
      vi.mocked(analyticsApi.getTopUsers).mockResolvedValue(mockTopUsers)

      const store = useAnalyticsStore()
      const promise = store.fetchAll()

      // Summary is still loading
      expect(store.isLoading).toBe(true)

      resolvePromise!(mockSummary)
      await promise

      expect(store.isLoading).toBe(false)
    })
  })

  // ============== exportData ==============

  describe('exportData', () => {
    it('does nothing when no data', () => {
      const store = useAnalyticsStore()

      // Mock URL.createObjectURL to detect if export tried
      const createObjectURL = vi.fn()
      vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })

      store.exportData()

      expect(createObjectURL).not.toHaveBeenCalled()
    })

    it('creates download when data exists', async () => {
      vi.mocked(analyticsApi.getSummary).mockResolvedValue(mockSummary)
      vi.mocked(analyticsApi.getTimeSeries).mockResolvedValue(mockTimeSeries)
      vi.mocked(analyticsApi.getTopUsers).mockResolvedValue(mockTopUsers)

      const store = useAnalyticsStore()
      await store.fetchAll()

      const createObjectURL = vi.fn(() => 'blob:test')
      const revokeObjectURL = vi.fn()
      vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })

      const clickSpy = vi.fn()
      vi.spyOn(document, 'createElement').mockReturnValue({
        href: '',
        download: '',
        click: clickSpy,
      } as unknown as HTMLAnchorElement)

      store.exportData()

      expect(createObjectURL).toHaveBeenCalled()
      expect(clickSpy).toHaveBeenCalled()
      expect(revokeObjectURL).toHaveBeenCalled()
    })
  })
})
