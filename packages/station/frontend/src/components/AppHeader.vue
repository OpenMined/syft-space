<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Inbox, Plus, Search, Server, ShieldCheck } from 'lucide-vue-next'
import SyftLogo from '@/assets/syftbox-logo.svg'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useStationStore } from '@/stores/station'

const props = defineProps<{
  /** Which view this header sits on — decided by the signed-in user's role. Omit when signed out. */
  variant?: 'member' | 'admin'
}>()

const emit = defineEmits<{ 'new-space': []; go: [section: 'requests' | 'spaces'] }>()

const station = useStationStore()

// ---- Search across spaces and open requests (admin only) ----
interface SearchResult {
  key: string
  name: string
  detail: string
  type: 'space' | 'request'
  icon: typeof Server
  section: 'requests' | 'spaces'
}

const searchQuery = ref('')
const searchFocused = ref(false)
const highlightedIndex = ref(0)

const searchResults = computed<SearchResult[]>(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return []
  const spaces = station.spaces
    .filter((s) => s.name.toLowerCase().includes(q) || s.ownerEmail.toLowerCase().includes(q))
    .map<SearchResult>((s) => ({
      key: `space-${s.id}`,
      name: s.name,
      detail: s.ownerEmail,
      type: 'space',
      icon: Server,
      section: 'spaces',
    }))
  const requests = station.requests
    .filter((r) => r.status === 'pending' || r.status === 'provisioning' || r.status === 'failed')
    .filter(
      (r) => r.spaceName.toLowerCase().includes(q) || r.requesterEmail.toLowerCase().includes(q),
    )
    .map<SearchResult>((r) => ({
      key: `request-${r.id}`,
      name: r.spaceName,
      detail: r.requesterEmail,
      type: 'request',
      icon: Inbox,
      section: 'requests',
    }))
  return [...spaces, ...requests].slice(0, 8)
})

const showDropdown = computed(() => searchFocused.value && searchQuery.value.trim().length > 0)

watch(searchResults, () => {
  highlightedIndex.value = 0
})

let blurTimer: ReturnType<typeof setTimeout> | null = null

function handleSearchBlur() {
  if (blurTimer) clearTimeout(blurTimer)
  blurTimer = setTimeout(() => {
    searchFocused.value = false
    blurTimer = null
  }, 150)
}

function selectResult(result: SearchResult) {
  emit('go', result.section)
  searchQuery.value = ''
  searchFocused.value = false
}

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
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, results.length - 1)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
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
</script>

<template>
  <header
    class="flex h-12 w-full shrink-0 items-center gap-4 border-b border-border/40 bg-background px-4"
  >
    <div class="flex min-w-0 flex-1 items-center gap-2">
      <img :src="SyftLogo" alt="Syft Station" class="h-8 w-8 shrink-0" />
      <span class="truncate text-sm font-semibold tracking-tight">Syft Station</span>
      <Badge v-if="props.variant === 'admin'" variant="contrast" class="gap-1">
        <ShieldCheck class="h-3 w-3" />
        Admin
      </Badge>
    </div>

    <div v-if="props.variant === 'admin'" class="relative w-full max-w-md">
      <Search
        class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        v-model="searchQuery"
        placeholder="Search spaces & requests..."
        class="h-8 border-transparent bg-muted/50 pl-8 pr-3 text-sm focus:border-border focus:bg-background"
        @focus="searchFocused = true"
        @blur="handleSearchBlur"
        @keydown="handleSearchKeydown"
      />
      <div
        v-if="showDropdown"
        class="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-md border border-border bg-popover shadow-md"
      >
        <div v-if="searchResults.length === 0" class="px-3 py-2 text-xs text-muted-foreground">
          No results for "{{ searchQuery }}"
        </div>
        <button
          v-for="(result, index) in searchResults"
          :key="result.key"
          class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-foreground transition-colors"
          :class="index === highlightedIndex ? 'bg-muted' : 'hover:bg-muted'"
          @mousedown.prevent="selectResult(result)"
          @mousemove="highlightedIndex = index"
        >
          <component :is="result.icon" class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span class="flex-1 truncate">{{ result.name }}</span>
          <span class="truncate text-xs text-muted-foreground">{{ result.detail }}</span>
          <span class="shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
            {{ result.type }}
          </span>
        </button>
      </div>
    </div>

    <div class="flex flex-1 items-center justify-end gap-2">
      <Button v-if="props.variant === 'admin'" size="sm" class="h-8" @click="emit('new-space')">
        <Plus class="mr-1 h-3.5 w-3.5" />
        New space
      </Button>
      <ThemeToggle />
    </div>
  </header>
</template>
