import { ref, computed } from 'vue'
import axios from 'axios'
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
  permissionDenied?: boolean
}

const TCC_SERVICE_MAP: Record<string, string> = {
  Documents: 'SystemPolicyDocumentsFolder',
  Desktop: 'SystemPolicyDesktopFolder',
  Downloads: 'SystemPolicyDownloadsFolder',
}

function getTccService(path: string): string | null {
  // Normalize: expand ~ to a generic home prefix for matching
  const normalized = path.replace(/^~/, '/Users/_home_')
  // Match the first directory component after home
  const match = normalized.match(/^\/Users\/[^/]+\/([^/]+)/)
  const folder = match?.[1]
  if (folder) {
    return TCC_SERVICE_MAP[folder] ?? null
  }
  return null
}

export function useDatasetBrowser() {
  const rootNodes = ref<FileNode[]>([])
  const loadingPaths = ref<Set<string>>(new Set())
  const loadedPaths = ref<Set<string>>(new Set())
  const error = ref<string | null>(null)
  const isInitialLoading = ref(false)
  const rootPermissionDenied = ref(false)

  const loadDirectory = async (
    path = '~',
    isInitial = false,
  ): Promise<{ nodes: FileNode[]; permissionDenied: boolean }> => {
    try {
      if (isInitial) {
        isInitialLoading.value = true
        error.value = null
      } else {
        loadingPaths.value.add(path)
      }

      const response = await datasetsApi.browse(path, false)

      if (!response || !Array.isArray(response.items)) {
        throw new Error('Invalid response from server')
      }

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
      return { nodes, permissionDenied: false }
    } catch (err) {
      const is403 = axios.isAxiosError(err) && err.response?.status === 403
      if (isInitial) {
        error.value = is403
          ? 'Permission denied'
          : err instanceof Error
            ? err.message
            : 'Failed to load directory'
      }
      return { nodes: [], permissionDenied: is403 }
    } finally {
      if (isInitial) {
        isInitialLoading.value = false
      } else {
        loadingPaths.value.delete(path)
      }
    }
  }

  const loadRootDirectory = async () => {
    rootPermissionDenied.value = false
    const result = await loadDirectory('~', true)
    rootNodes.value = result.nodes
    rootPermissionDenied.value = result.permissionDenied
  }

  const loadSubdirectory = async (parentNode: FileNode) => {
    if (
      parentNode.type !== 'directory' ||
      (parentNode.hasLoaded && !parentNode.permissionDenied)
    ) {
      return
    }

    parentNode.isLoading = true
    parentNode.permissionDenied = false
    try {
      const result = await loadDirectory(parentNode.path)
      parentNode.children = result.nodes
      parentNode.hasLoaded = true
      parentNode.permissionDenied = result.permissionDenied
    } finally {
      parentNode.isLoading = false
    }
  }

  const resetTccPermission = async (service: string) => {
    if (window.__TAURI__) {
      await window.__TAURI__.core.invoke('reset_tcc_permission', { service })
    }
  }

  const retryDirectory = async (node: FileNode) => {
    const service = getTccService(node.path)
    if (service) {
      await resetTccPermission(service)
    }
    node.hasLoaded = false
    node.permissionDenied = false
    await loadSubdirectory(node)
  }

  const retryRootDirectory = async () => {
    rootPermissionDenied.value = false
    await loadRootDirectory()
  }

  const isLoading = computed(() => {
    return isInitialLoading.value || loadingPaths.value.size > 0
  })

  return {
    rootNodes,
    error,
    isLoading,
    isInitialLoading,
    rootPermissionDenied,
    loadRootDirectory,
    loadSubdirectory,
    retryDirectory,
    retryRootDirectory,
  }
}
