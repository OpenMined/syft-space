import { defineStore } from 'pinia'
import { ref } from 'vue'
import { DATA_SOURCE_TYPES, MODEL_TYPES, type ValueOf } from '@/lib/constants'
import { endpointsApi } from '@/api/endpoints/endpoints'
import type { EndpointListItem } from '@/api/types'

export interface EndpointItem {
  id: string
  name: string
  summary: string
  description: string
  dataSourceType?: ValueOf<typeof DATA_SOURCE_TYPES>
  modelType?: ValueOf<typeof MODEL_TYPES>
  price: string
  languages: string[]
  domains: string[]
  mcpCompatible: boolean
  tags: string[]
  published: boolean
  watchedPaths?: string[]
}

export const useEndpointsStore = defineStore('endpoints', () => {
  const endpoints = ref<EndpointItem[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Transform API response to frontend model
  const transformEndpointListItem = (item: EndpointListItem): EndpointItem => {
    // Extract domain from tags if present
    const tagList = item.tags ? item.tags.split(',').map(t => t.trim()) : []
    const domainTag = tagList.find(tag => tag.startsWith('domain:'))
    const domain = domainTag ? domainTag.replace('domain:', '') : undefined
    
    return {
      id: item.id,
      name: item.name,
      summary: item.summary,
      description: '', // Not provided in list API
      dataSourceType: undefined, // Would need to fetch from dataset details
      modelType: undefined, // Would need to fetch from model details
      price: '$0.00 - $0.00 / request', // Default, not provided by API
      languages: [], // Default, not provided by API
      domains: domain ? [domain] : [], // Extract from tags
      mcpCompatible: false, // Default, not provided by API
      tags: tagList,
      published: item.published,
      watchedPaths: undefined, // Not provided in list API
    }
  }

  const fetchEndpoints = async () => {
    isLoading.value = true
    error.value = null
    try {
      const response = await endpointsApi.list()
      endpoints.value = response.map(transformEndpointListItem)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch endpoints'
      console.error('Failed to fetch endpoints:', err)
    } finally {
      isLoading.value = false
    }
  }

  return {
    endpoints,
    isLoading,
    error,
    fetchEndpoints,
  }
})
