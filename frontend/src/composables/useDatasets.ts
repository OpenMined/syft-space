import { ref } from 'vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { DatasetListItem } from '@/api/types'

export function useDatasets() {
  const datasets = ref<DatasetListItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const loadDatasets = async () => {
    loading.value = true
    error.value = null
    
    try {
      const data = await datasetsApi.list()
      datasets.value = data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load datasets'
    } finally {
      loading.value = false
    }
  }

  const deleteDataset = async (name: string) => {
    try {
      await datasetsApi.delete(name)
      // Remove from local state
      datasets.value = datasets.value.filter(dataset => dataset.name !== name)
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete dataset'
      return false
    }
  }

  const refreshDatasets = () => {
    return loadDatasets()
  }

  // Transform API data to match the existing component interface
  const transformDataset = (dataset: DatasetListItem) => {
    return {
      id: dataset.id,
      name: dataset.name,
      type: dataset.dtype,
      description: dataset.summary || 'No description provided',
      tags: dataset.tags ? dataset.tags.split(',').map(tag => tag.trim()).filter(Boolean) : [],
      status: 'running' as 'running' | 'stopped', // Default status since API doesn't provide this
      endpointCount: 0, // Default endpoint count since API doesn't provide this
      watchedPaths: [], // Default empty paths since API doesn't provide this
      isCustom: dataset.dtype !== 'local_file', // Consider non-local_file as custom
    }
  }

  return {
    datasets,
    loading,
    error,
    loadDatasets,
    deleteDataset,
    refreshDatasets,
    transformDataset,
  }
}