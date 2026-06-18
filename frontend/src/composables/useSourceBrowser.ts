import { ref, computed } from 'vue'
import axios from 'axios'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { SourceItem } from '@/api/types'

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
  /** Source-specific status (e.g. WordPress 'publish' | 'private'). */
  status?: string
  /** External URL to preview the item, if the source provides one. */
  link?: string
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

export function useSourceBrowser(
  dtype: string,
  configuration: Record<string, unknown> = {},
) {
  const rootNodes = ref<FileNode[]>([])
  const loadingPaths = ref<Set<string>>(new Set())
  const loadedPaths = ref<Set<string>>(new Set())
  const error = ref<string | null>(null)
  const isInitialLoading = ref(false)
  const rootPermissionDenied = ref(false)

  const loadDirectory = async (
    parentId: string | null,
    isInitial = false,
  ): Promise<{ nodes: FileNode[]; permissionDenied: boolean }> => {
    const loadingKey = parentId ?? '__root__'
    try {
      if (isInitial) {
        isInitialLoading.value = true
        error.value = null
      } else {
        loadingPaths.value.add(loadingKey)
      }

      const response = await datasetsApi.browse(dtype, parentId, configuration)

      if (!response || !Array.isArray(response.items)) {
        throw new Error('Invalid response from server')
      }

      const nodes: FileNode[] = response.items.map((item: SourceItem) => {
        const modified =
          (item.metadata?.modified_gmt as string | undefined) ??
          (item.metadata?.modified as string | undefined)
        return {
          name: item.display_name,
          path: item.external_id,
          type: item.is_container ? 'directory' : 'file',
          size: item.size_bytes ?? undefined,
          modifiedTime: modified ? new Date(modified) : undefined,
          children: item.is_container ? [] : undefined,
          hasLoaded: false,
          status: (item.metadata?.status as string | undefined) ?? undefined,
          link: (item.metadata?.link as string | undefined) ?? undefined,
        }
      })

      loadedPaths.value.add(loadingKey)
      return { nodes, permissionDenied: false }
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined
      // The backend sends a user-facing reason in `detail` (e.g. "Authentication
      // failed (401)…"); prefer it so the picker says why, not just "failed".
      const detail = axios.isAxiosError(err)
        ? (err.response?.data?.detail as string | undefined)
        : undefined
      const is403 = status === 403
      if (isInitial) {
        error.value =
          detail ??
          (is403
            ? 'Permission denied'
            : err instanceof Error
              ? err.message
              : 'Failed to load directory')
      }
      return { nodes: [], permissionDenied: is403 }
    } finally {
      if (isInitial) {
        isInitialLoading.value = false
      } else {
        loadingPaths.value.delete(loadingKey)
      }
    }
  }

  const loadRootDirectory = async () => {
    rootPermissionDenied.value = false
    const result = await loadDirectory(null, true)
    rootNodes.value = result.nodes
    rootPermissionDenied.value = result.permissionDenied
  }

  const loadSubdirectory = async (parentNode: FileNode) => {
    if (parentNode.type !== 'directory' || (parentNode.hasLoaded && !parentNode.permissionDenied)) {
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
