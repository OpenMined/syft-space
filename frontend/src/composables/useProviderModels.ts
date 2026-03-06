import { ref, watch, type Ref } from 'vue'
import { modelsApi } from '@/api/endpoints/models'
import type { ProviderModelItem } from '@/api/types'

export function useProviderModels(baseUrl: Ref<string>, apiKey: Ref<string>) {
  const models = ref<ProviderModelItem[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const hasFetched = ref(false)
  let requestVersion = 0
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  const resetState = () => {
    models.value = []
    error.value = null
    hasFetched.value = false
    isLoading.value = false
  }

  const fetchModels = async () => {
    const baseUrlVal = baseUrl.value
    const apiKeyVal = apiKey.value

    if (!baseUrlVal || !apiKeyVal.trim()) {
      requestVersion += 1
      resetState()
      return
    }

    const currentRequestVersion = ++requestVersion
    isLoading.value = true
    error.value = null

    try {
      const response = await modelsApi.fetchProviderModels({
        base_url: baseUrlVal,
        api_key: apiKeyVal,
      })

      if (currentRequestVersion !== requestVersion) {
        return
      }

      models.value = response.models
      hasFetched.value = true
    } catch (err: unknown) {
      if (currentRequestVersion !== requestVersion) {
        return
      }

      models.value = []
      hasFetched.value = false
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } }
        error.value = axiosError.response?.data?.detail ?? 'Failed to fetch models'
      } else if (err instanceof Error) {
        error.value = err.message
      } else {
        error.value = 'Failed to fetch models'
      }
    } finally {
      if (currentRequestVersion === requestVersion) {
        isLoading.value = false
      }
    }
  }

  const debouncedFetch = (delay = 300) => {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      fetchModels()
    }, delay)
  }

  // Reset when base URL changes
  watch(baseUrl, () => {
    requestVersion += 1
    resetState()
  })

  // Auto-fetch when API key changes (debounced)
  watch(apiKey, (newKey) => {
    if (debounceTimer) clearTimeout(debounceTimer)
    requestVersion += 1
    resetState()

    if (newKey.trim() && baseUrl.value) {
      debouncedFetch(500)
    }
  })

  return {
    models,
    isLoading,
    error,
    hasFetched,
    fetchModels,
  }
}
