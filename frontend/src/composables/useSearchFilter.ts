/**
 * Composable for optimized search and filtering operations
 * Provides efficient filtering with caching and debouncing
 */

import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'
import { UI_CONSTANTS } from '@/lib/constants'

export interface FilterableItem {
  [key: string]: unknown
}

export interface SearchConfig<T extends FilterableItem> {
  searchFields: (keyof T)[]
  statusField?: keyof T
  tagsField?: keyof T
  debounceMs?: number
}

export function useSearchFilter<T extends FilterableItem>(
  items: Ref<T[]>,
  config: SearchConfig<T>,
) {
  const searchQuery = ref('')
  const activeStatus = ref('all')
  const debouncedQuery = ref('')

  let debounceTimeout: ReturnType<typeof setTimeout> | null = null

  // Debounced search query
  watch(
    searchQuery,
    (newQuery) => {
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }

      debounceTimeout = setTimeout(() => {
        debouncedQuery.value = newQuery
      }, config.debounceMs || UI_CONSTANTS.DEFAULT_SEARCH_DEBOUNCE_MS)
    },
    { immediate: true },
  )

  // Pre-computed search terms for better performance
  const searchTerms = computed(() => {
    const query = debouncedQuery.value.toLowerCase().trim()
    return query ? query.split(' ').filter((term) => term.length > 0) : []
  })

  // Optimized filtering with single pass
  const filteredItems = computed(() => {
    const terms = searchTerms.value
    const status = activeStatus.value

    if (terms.length === 0 && status === 'all') {
      return items.value
    }

    return items.value.filter((item) => {
      // Status filter
      if (status !== 'all' && config.statusField) {
        if (item[config.statusField] !== status) {
          return false
        }
      }

      // Search filter
      if (terms.length > 0) {
        let searchText = config.searchFields
          .map((field) => String(item[field] || '').toLowerCase())
          .join(' ')

        // Include tags if specified
        if (config.tagsField && Array.isArray(item[config.tagsField])) {
          const tags = (item[config.tagsField] as string[])
            .map((tag) => tag.toLowerCase())
            .join(' ')
          searchText += ' ' + tags
        }

        // All terms must match
        const matches = terms.every((term) => searchText.includes(term))
        if (!matches) {
          return false
        }
      }

      return true
    })
  })

  // Stats for UI
  const totalCount = computed(() => items.value.length)
  const filteredCount = computed(() => filteredItems.value.length)
  const hasFilters = computed(() => searchTerms.value.length > 0 || activeStatus.value !== 'all')

  // Clear filters
  const clearFilters = () => {
    searchQuery.value = ''
    activeStatus.value = 'all'
  }

  // Cleanup
  const cleanup = () => {
    if (debounceTimeout) {
      clearTimeout(debounceTimeout)
    }
  }

  return {
    // State
    searchQuery,
    activeStatus,

    // Computed
    filteredItems,
    totalCount,
    filteredCount,
    hasFilters,

    // Methods
    clearFilters,
    cleanup,
  }
}
