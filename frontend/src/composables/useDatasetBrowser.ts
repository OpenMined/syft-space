import { ref, computed } from 'vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { FileItem } from '@/api/types'

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  modifiedTime?: Date
  children?: FileNode[]
  isLoading?: boolean
  hasLoaded?: boolean
}

export function useDatasetBrowser() {
  const rootNodes = ref<FileNode[]>([])
  const loadingPaths = ref<Set<string>>(new Set())
  const loadedPaths = ref<Set<string>>(new Set())
  const error = ref<string | null>(null)
  const isInitialLoading = ref(false)

  const loadDirectory = async (path = '~', isInitial = false): Promise<FileNode[]> => {
    try {
      if (isInitial) {
        isInitialLoading.value = true
      } else {
        loadingPaths.value.add(path)
      }
      
      error.value = null
      const response = await datasetsApi.browse(path, false)
      
      if (!response || !Array.isArray(response.items)) {
        throw new Error('Invalid response from server')
      }
      
      // Convert API response to FileNode format
      const nodes: FileNode[] = response.items.map((item: FileItem) => ({
        name: item.name,
        path: item.path,
        type: item.is_dir ? 'directory' : 'file',
        size: item.size,
        modifiedTime: item.modified ? new Date(item.modified) : undefined,
        children: item.is_dir ? [] : undefined,
        hasLoaded: false,
      }))
      
      loadedPaths.value.add(path)
      return nodes
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load directory'
      return []
    } finally {
      if (isInitial) {
        isInitialLoading.value = false
      } else {
        loadingPaths.value.delete(path)
      }
    }
  }

  const loadRootDirectory = async () => {
    rootNodes.value = await loadDirectory('~', true)
  }

  const loadSubdirectory = async (parentNode: FileNode) => {
    if (parentNode.type !== 'directory' || parentNode.hasLoaded) {
      return
    }

    parentNode.isLoading = true
    try {
      const children = await loadDirectory(parentNode.path)
      parentNode.children = children
      parentNode.hasLoaded = true
    } finally {
      parentNode.isLoading = false
    }
  }

  const isLoading = computed(() => {
    return isInitialLoading.value || loadingPaths.value.size > 0
  })

  return {
    rootNodes,
    error,
    isLoading,
    isInitialLoading,
    loadRootDirectory,
    loadSubdirectory,
  }
}