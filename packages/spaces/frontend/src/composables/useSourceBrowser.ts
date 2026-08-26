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
  /** Cursor for the next page of this container's children; null when exhausted. */
  nextCursor?: string | null
  /** True while a "load more" fetch for this container is in flight. */
  isLoadingMore?: boolean
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
  // When set, browse an existing dataset's source server-side (stored
  // credentials) instead of passing client-supplied configuration.
  datasetName?: string,
) {
  const rootNodes = ref<FileNode[]>([])
  const rootNextCursor = ref<string | null>(null)
  const rootLoadingMore = ref(false)
  const loadingPaths = ref<Set<string>>(new Set())
  const loadedPaths = ref<Set<string>>(new Set())
  const error = ref<string | null>(null)
  const isInitialLoading = ref(false)
  const rootPermissionDenied = ref(false)

  const loadDirectory = async (
    parentId: string | null,
    isInitial = false,
    cursor: string | null = null,
  ): Promise<{
    nodes: FileNode[]
    permissionDenied: boolean
    nextCursor: string | null
    ok: boolean
  }> => {
    const loadingKey = parentId ?? '__root__'
    try {
      if (isInitial) {
        isInitialLoading.value = true
        error.value = null
      } else {
        loadingPaths.value.add(loadingKey)
      }

      const response = datasetName
        ? await datasetsApi.browseDataset(datasetName, parentId, cursor)
        : await datasetsApi.browse(dtype, parentId, configuration, cursor)

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
          // Sources name this differently — WordPress sends `link`,
          // Blogger sends `url`.
          link:
            (item.metadata?.link as string | undefined) ??
            (item.metadata?.url as string | undefined) ??
            undefined,
        }
      })

      loadedPaths.value.add(loadingKey)
      return {
        nodes,
        permissionDenied: false,
        nextCursor: response.next_cursor ?? null,
        ok: true,
      }
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
      return { nodes: [], permissionDenied: is403, nextCursor: null, ok: false }
    } finally {
      if (isInitial) {
        isInitialLoading.value = false
      } else {
        loadingPaths.value.delete(loadingKey)
      }
    }
  }

  /** Append nodes not already present (dedup by path) into an existing list. */
  const appendDeduped = (existing: FileNode[], incoming: FileNode[]) => {
    const seen = new Set(existing.map((n) => n.path))
    for (const node of incoming) {
      if (!seen.has(node.path)) {
        existing.push(node)
        seen.add(node.path)
      }
    }
  }

  const loadRootDirectory = async () => {
    rootPermissionDenied.value = false
    const result = await loadDirectory(null, true)
    rootNodes.value = result.nodes
    rootNextCursor.value = result.nextCursor
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
      parentNode.nextCursor = result.nextCursor
      parentNode.hasLoaded = true
      parentNode.permissionDenied = result.permissionDenied
    } finally {
      parentNode.isLoading = false
    }
  }

  /** Fetch the next page of a container's children and append it. */
  const loadMore = async (node: FileNode) => {
    if (!node.nextCursor || node.isLoadingMore) {
      return
    }
    node.isLoadingMore = true
    try {
      const result = await loadDirectory(node.path, false, node.nextCursor)
      if (result.ok) {
        if (!node.children) {
          node.children = []
        }
        appendDeduped(node.children, result.nodes)
        node.nextCursor = result.nextCursor
      }
    } finally {
      node.isLoadingMore = false
    }
  }

  /** Fetch the next page of the root level and append it. */
  const loadMoreRoot = async () => {
    if (!rootNextCursor.value || rootLoadingMore.value) {
      return
    }
    rootLoadingMore.value = true
    try {
      const result = await loadDirectory(null, false, rootNextCursor.value)
      if (result.ok) {
        appendDeduped(rootNodes.value, result.nodes)
        rootNextCursor.value = result.nextCursor
      }
    } finally {
      rootLoadingMore.value = false
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
    rootNextCursor,
    rootLoadingMore,
    error,
    isLoading,
    isInitialLoading,
    rootPermissionDenied,
    loadRootDirectory,
    loadSubdirectory,
    loadMore,
    loadMoreRoot,
    retryDirectory,
    retryRootDirectory,
  }
}
