<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRouter, type RouteLocationRaw } from 'vue-router'
import { toast } from 'vue-sonner'
import { Database, Brain, Globe, Search } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { useNavigation } from '@/composables/useNavigation'
import { useEndpointsStore } from '@/stores/endpoints'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'
import { parseTags } from '@/lib/formatters'

const router = useRouter()
const { routes } = useNavigation()
const endpointsStore = useEndpointsStore()

const searchQuery = ref('')
const searchFocused = ref(false)
const highlightedIndex = ref(0)
const SEARCH_RESULT_ID_PREFIX = 'topbar-search-result-'
const RESOURCE_CACHE_TTL_MS = 30_000

interface SearchResult {
  name: string
  summary: string
  tags: string[]
  type: 'data-source' | 'model' | 'api'
  icon: typeof Database
  route: RouteLocationRaw
}

const allResources = ref<SearchResult[]>([])
const lastLoadedAt = ref(0)
let inFlightLoad: Promise<void> | null = null

async function loadResources(force = false): Promise<void> {
  if (inFlightLoad) return inFlightLoad
  const isFresh = Date.now() - lastLoadedAt.value < RESOURCE_CACHE_TTL_MS
  if (!force && lastLoadedAt.value > 0 && isFresh) return

  inFlightLoad = (async () => {
    try {
      const [datasets, models] = await Promise.all([datasetsApi.list(), modelsApi.list()])
      const results: SearchResult[] = []
      for (const d of datasets) {
        results.push({
          name: d.name,
          summary: d.summary ?? '',
          tags: parseTags(d.tags),
          type: 'data-source',
          icon: Database,
          route: routes.datasetDetail(d.name),
        })
      }
      for (const m of models) {
        results.push({
          name: m.name,
          summary: m.summary ?? '',
          tags: parseTags(m.tags),
          type: 'model',
          icon: Brain,
          route: routes.modelDetail(m.name),
        })
      }
      for (const e of endpointsStore.endpoints) {
        results.push({
          name: e.name,
          summary: e.summary ?? '',
          tags: parseTags(e.tags),
          type: 'api',
          icon: Globe,
          route: routes.endpointDetail(e.slug),
        })
      }
      allResources.value = results
      lastLoadedAt.value = Date.now()
    } catch (err) {
      console.error('Failed to load topbar resources for search:', err)
      toast.error('Could not load resources')
    } finally {
      inFlightLoad = null
    }
  })()

  return inFlightLoad
}

const searchResults = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return []
  return allResources.value
    .filter((r) => {
      if (r.name.toLowerCase().includes(q)) return true
      if (r.summary.toLowerCase().includes(q)) return true
      return r.tags.some((t) => t.toLowerCase().includes(q))
    })
    .slice(0, 8)
})

const showDropdown = computed(() => searchFocused.value && searchQuery.value.trim().length > 0)

const activeDescendantId = computed(() => {
  if (!showDropdown.value || searchResults.value.length === 0) return undefined
  return `${SEARCH_RESULT_ID_PREFIX}${highlightedIndex.value}`
})

function handleSearchFocus() {
  searchFocused.value = true
  void loadResources()
}

function selectResult(result: SearchResult) {
  router.push(result.route)
  searchQuery.value = ''
  searchFocused.value = false
}

let blurTimer: ReturnType<typeof setTimeout> | null = null
function handleSearchBlur() {
  if (blurTimer) clearTimeout(blurTimer)
  blurTimer = setTimeout(() => {
    searchFocused.value = false
    blurTimer = null
  }, 150)
}

onBeforeUnmount(() => {
  if (blurTimer) clearTimeout(blurTimer)
})

function handleSearchKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    searchQuery.value = ''
    ;(event.target as HTMLInputElement | null)?.blur()
    return
  }
  if (!showDropdown.value) return
  const results = searchResults.value
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (results.length === 0) return
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, results.length - 1)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (results.length === 0) return
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
    return
  }
  if (event.key === 'Enter') {
    const result = results[highlightedIndex.value]
    if (!result) return
    event.preventDefault()
    selectResult(result)
  }
}

watch(searchResults, () => {
  highlightedIndex.value = 0
})
</script>

<template>
  <header class="flex items-center h-16 px-4 bg-background shrink-0">
    <div class="flex-1" />
    <div class="relative w-full max-w-md">
      <Search
        class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none"
      />
      <Input
        v-model="searchQuery"
        placeholder="Search resources..."
        class="h-8 pl-8 pr-3 text-sm bg-muted/50 border-transparent focus:border-border focus:bg-background"
        role="combobox"
        :aria-expanded="showDropdown"
        aria-controls="topbar-search-results"
        aria-autocomplete="list"
        :aria-activedescendant="activeDescendantId"
        @focus="handleSearchFocus"
        @blur="handleSearchBlur"
        @keydown="handleSearchKeydown"
      />
      <div
        v-if="showDropdown"
        id="topbar-search-results"
        role="listbox"
        class="absolute left-0 right-0 top-full mt-1 bg-popover border border-border rounded-md shadow-md z-50 overflow-hidden"
      >
        <div v-if="searchResults.length === 0" class="px-3 py-2 text-xs text-muted-foreground">
          No results for "{{ searchQuery }}"
        </div>
        <button
          v-for="(result, index) in searchResults"
          :id="`topbar-search-result-${index}`"
          :key="`${result.type}-${result.name}`"
          role="option"
          :aria-selected="index === highlightedIndex"
          class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-foreground transition-colors text-left"
          :class="index === highlightedIndex ? 'bg-muted' : 'hover:bg-muted'"
          @mousedown.prevent="selectResult(result)"
          @mousemove="highlightedIndex = index"
        >
          <component :is="result.icon" class="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span class="truncate flex-1">{{ result.name }}</span>
          <span class="text-[10px] text-muted-foreground shrink-0 uppercase tracking-wider">{{
            result.type === 'data-source' ? 'data' : result.type
          }}</span>
        </button>
      </div>
    </div>
    <div class="flex-1 flex justify-end">
      <ThemeToggle />
    </div>
  </header>
</template>
