import { defineStore } from 'pinia'
import { ref } from 'vue'
import { DATA_SOURCE_TYPES, MODEL_TYPES, type ValueOf } from '@/lib/constants'
import { endpointsApi } from '@/api/endpoints/endpoints'
import type { EndpointListItem } from '@/api/types'

export interface EndpointItem {
  id: string
  name: string
  slug: string
  summary: string
  description: string
  dataSourceType?: ValueOf<typeof DATA_SOURCE_TYPES>
  modelType?: ValueOf<typeof MODEL_TYPES>
  modelId?: string
  datasetId?: string
  systemPrompt?: string | null
  price: string
  languages: string[]
  domains: string[]
  mcpCompatible: boolean
  tags: string[]
  published: boolean
  watchedPaths?: string[]
  createdAt: string
}

const FRESHNESS_MS = 30_000

export const useEndpointsStore = defineStore('endpoints', () => {
  const endpoints = ref<EndpointItem[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  let lastLoadedAt = 0
  let inFlight: Promise<void> | null = null

  // Transform API response to frontend model
  const transformEndpointListItem = (item: EndpointListItem): EndpointItem => {
    // Extract domain from tags if present
    const tagList = item.tags ? item.tags.split(',').map((t) => t.trim()) : []
    const domainTag = tagList.find((tag) => tag.startsWith('domain:'))
    const domain = domainTag ? domainTag.replace('domain:', '') : undefined

    // Extract watched paths from dataset configuration
    let watchedPaths: string[] | undefined = undefined
    if (
      item.dataset?.configuration?.filePaths &&
      Array.isArray(item.dataset.configuration.filePaths)
    ) {
      watchedPaths = (
        item.dataset.configuration.filePaths as Array<{ path: string; description: string }>
      ).map((fp) => fp.path)
    }

    return {
      id: item.id,
      name: item.name,
      slug: item.slug,
      summary: item.summary,
      description: '',
      dataSourceType: item.dataset?.dtype as ValueOf<typeof DATA_SOURCE_TYPES>,
      modelType: item.model?.dtype as ValueOf<typeof MODEL_TYPES>,
      modelId: item.model?.id,
      datasetId: item.dataset?.id,
      systemPrompt: item.system_prompt ?? null,
      price: '$0.00 - $0.00 / request',
      languages: [],
      domains: domain ? [domain] : [],
      mcpCompatible: false,
      tags: tagList,
      published: item.published,
      watchedPaths,
      createdAt: item.created_at,
    }
  }

  const fetchEndpoints = async (options: { force?: boolean } = {}): Promise<void> => {
    if (inFlight) return inFlight
    if (!options.force && Date.now() - lastLoadedAt < FRESHNESS_MS) return
    isLoading.value = true
    error.value = null
    inFlight = (async () => {
      try {
        const response = await endpointsApi.list()
        endpoints.value = response.map(transformEndpointListItem)
        lastLoadedAt = Date.now()
      } catch (err) {
        error.value = err instanceof Error ? err.message : 'Failed to fetch endpoints'
        console.error('Failed to fetch endpoints:', err)
      } finally {
        isLoading.value = false
        inFlight = null
      }
    })()
    return inFlight
  }

  const invalidate = () => {
    lastLoadedAt = 0
  }

  return {
    endpoints,
    isLoading,
    error,
    fetchEndpoints,
    invalidate,
  }
})
