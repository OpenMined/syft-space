import { ref } from 'vue'
import { analyticsApi } from '@/api/endpoints/analytics'
import type { SummaryStatsResponse } from '@/api/types/analytics'

/**
 * Loads the analytics summary for the home dashboard's metric cards.
 *
 * Uses a fixed 7-day window and its own state rather than the shared
 * useAnalyticsStore, whose time range is page-filter-driven (defaults to 30d)
 * and would couple the dashboard widget to the AnalyticsPage filter.
 */
export function useDashboardSummary() {
  const summary = ref<SummaryStatsResponse | null>(null)
  const loaded = ref(false)

  const load = async () => {
    loaded.value = false
    try {
      summary.value = await analyticsApi.getSummary({ time_range: '7d' })
    } catch {
      summary.value = null
    } finally {
      loaded.value = true
    }
  }

  return { summary, loaded, load }
}
