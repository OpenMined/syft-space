import { ref, onMounted } from 'vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'
import { endpointsApi } from '@/api/endpoints/endpoints'

export function useDashboardStats() {
  const datasetCount = ref(0)
  const modelCount = ref(0)
  const endpointCount = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const loadStats = async () => {
    loading.value = true
    error.value = null

    try {
      const [datasets, models, endpoints] = await Promise.all([
        datasetsApi.list().catch(() => []),
        modelsApi.list().catch(() => []),
        endpointsApi.list().catch(() => []),
      ])

      datasetCount.value = datasets.length
      modelCount.value = models.length
      endpointCount.value = endpoints.length
    } catch (e) {
      error.value = 'Failed to load dashboard statistics'
      console.error('Dashboard stats error:', e)
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    loadStats()
  })

  return {
    datasetCount,
    modelCount,
    endpointCount,
    loading,
    error,
    loadStats,
    refreshStats: loadStats,
  }
}
