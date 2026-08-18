import { ref } from 'vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { DatasetListItem, DatasetResponse, UpdateDatasetRequest } from '@/api/types'

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
      datasets.value = datasets.value.filter((dataset) => dataset.name !== name)
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete dataset'
      return false
    }
  }

  const getDataset = async (name: string): Promise<DatasetResponse | null> => {
    try {
      const dataset = await datasetsApi.get(name)
      return dataset
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to get dataset'
      return null
    }
  }

  const updateDataset = async (
    name: string,
    updateData: UpdateDatasetRequest,
  ): Promise<boolean> => {
    try {
      await datasetsApi.update(name, updateData)
      // Refresh the dataset list after update
      await loadDatasets()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update dataset'
      return false
    }
  }

  const refreshDatasets = () => {
    return loadDatasets()
  }

  // Transform API data to match the existing component interface
  const transformDataset = (dataset: DatasetListItem) => {
    // The list ships a short preview + total count of the selection rows, not
    // the full array — so a source watching many picks never bloats the list.
    const watchedPaths: string[] = (dataset.selected_items_preview || []).map(
      (item) => item.item_id,
    )
    const watchedPathsCount = dataset.selected_items_count ?? watchedPaths.length

    // Determine status from provisioner_status
    let status: 'running' | 'stopped' = 'stopped'
    if (dataset.provisioner_status) {
      const provStatus = dataset.provisioner_status.status.toLowerCase()
      if (provStatus === 'running' || provStatus === 'starting') {
        status = 'running'
      }
    }

    return {
      id: dataset.id,
      name: dataset.name,
      type: dataset.dtype,
      description: dataset.summary || 'No description provided',
      tags: dataset.tags
        ? dataset.tags
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean)
        : [],
      status, // Use actual provisioner status
      endpointCount: dataset.connected_endpoints?.length || 0, // Use actual endpoint count
      watchedPaths, // Preview subset of the dataset_selection rows
      watchedPathsCount, // Total selection-row count (for the "+N more" affordance)
      isCustom: dataset.dtype !== 'local_file', // Consider non-local_file as custom
      configuration: dataset.configuration, // Pass through full configuration
      connected_endpoints: dataset.connected_endpoints || [], // Include endpoints for later use
    }
  }

  return {
    datasets,
    loading,
    error,
    loadDatasets,
    getDataset,
    updateDataset,
    deleteDataset,
    refreshDatasets,
    transformDataset,
  }
}
