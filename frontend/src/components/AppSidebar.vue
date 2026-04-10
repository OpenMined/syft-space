<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute, type RouteLocationRaw } from 'vue-router'
import { toast } from 'vue-sonner'
import {
  LayoutDashboard,
  Database,
  Brain,
  Globe,
  Inbox,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  User,
  Plus,
  Search,
  MessageSquare,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Separator } from '@/components/ui/separator'
import { useSidebar } from '@/composables/useSidebar'
import { useNavigation } from '@/composables/useNavigation'
import { useInboxStore } from '@/stores/inbox'
import { useUserStore } from '@/stores/user'
import { useEndpointsStore } from '@/stores/endpoints'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'
import SyftLogo from '@/assets/syftbox-logo.svg'
import ThemeToggle from '@/components/ThemeToggle.vue'

const router = useRouter()
const route = useRoute()
const { isCollapsed, toggle } = useSidebar()
const { routes } = useNavigation()
const inboxStore = useInboxStore()
const userStore = useUserStore()
const endpointsStore = useEndpointsStore()

const liveCount = computed(() => endpointsStore.endpoints.filter((e) => e.published).length)

const searchQuery = ref('')
const searchFocused = ref(false)
const highlightedIndex = ref(0)
const SEARCH_RESULT_ID_PREFIX = 'sidebar-search-result-'
const RESOURCE_CACHE_TTL_MS = 30_000

interface SearchResult {
  name: string
  summary: string
  tags: string[]
  type: 'data-source' | 'model' | 'api'
  icon: typeof Database
  route: RouteLocationRaw
}

function parseTags(raw: string | string[] | undefined): string[] {
  if (!raw) return []
  if (Array.isArray(raw)) return raw.map((t) => t.trim()).filter(Boolean)
  return raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
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
          route: routes.dataSourceDetail(d.name),
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
          route: routes.liveDetail(e.slug),
        })
      }
      allResources.value = results
      lastLoadedAt.value = Date.now()
    } catch (err) {
      console.error('Failed to load sidebar resources for search:', err)
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

function handleSearchBlur() {
  setTimeout(() => {
    searchFocused.value = false
  }, 150)
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

const routeMapping: Record<string, string[]> = {
  home: ['home'],
  datasets: ['datasets', 'dataset-detail'],
  models: ['models', 'model-detail'],
  chat: ['chat'],
  endpoints: ['endpoints', 'endpoint-detail'],
  inbox: ['inbox'],
  analytics: ['analytics'],
  settings: ['settings'],
}

const isActive = (navId: string) => {
  const mapped = routeMapping[navId]
  return mapped ? mapped.includes(route.name as string) : false
}

const navigateTo = (routeName: string) => {
  router.push({ name: routeName })
}

interface NavItem {
  id: string
  route: string
  label: string
  icon: typeof LayoutDashboard
  badge?: () => number | string | undefined
  badgeVariant?: 'default' | 'destructive' | 'secondary' | 'outline'
}

const mainNav: NavItem[] = [{ id: 'home', route: 'home', label: 'Home', icon: LayoutDashboard }]

const resourceNav: NavItem[] = [
  { id: 'datasets', route: 'datasets', label: 'Data Sources', icon: Database },
  { id: 'models', route: 'models', label: 'Models', icon: Brain },
  { id: 'chat', route: 'chat', label: 'Chat', icon: MessageSquare },
]

const liveNav: NavItem[] = [
  {
    id: 'endpoints',
    route: 'endpoints',
    label: 'APIs',
    icon: Globe,
    badge: () => (liveCount.value > 0 ? liveCount.value : undefined),
    badgeVariant: 'secondary',
  },
]

const bottomNav: NavItem[] = [
  {
    id: 'inbox',
    route: 'inbox',
    label: 'Inbox',
    icon: Inbox,
    badge: () => (inboxStore.unreadCount > 0 ? inboxStore.unreadCount : undefined),
    badgeVariant: 'destructive',
  },
  { id: 'settings', route: 'settings', label: 'Settings', icon: Settings },
]

const renderNavItem = (item: NavItem) => ({
  ...item,
  active: isActive(item.id),
  badgeValue: item.badge?.(),
})
</script>

<template>
  <aside
    class="flex flex-col h-full bg-background border-r border-border/40 transition-all duration-200 ease-in-out"
    :class="isCollapsed ? 'w-16' : 'w-60'"
  >
    <!-- Logo -->
    <div class="flex items-center justify-between h-16 px-4 border-b border-border shrink-0">
      <button class="flex items-center gap-3 min-w-0" @click="navigateTo('home')">
        <img :src="SyftLogo" alt="Syft Space" class="h-7 w-7 shrink-0" />
        <span
          v-if="!isCollapsed"
          class="text-sm font-semibold text-foreground tracking-tight truncate"
        >
          Syft Space
        </span>
      </button>
      <div class="flex items-center gap-0.5">
        <ThemeToggle v-if="!isCollapsed" />
        <TooltipProvider :delay-duration="0">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="ghost" size="icon" class="h-8 w-8" @click="toggle">
                <ChevronsLeft v-if="!isCollapsed" class="h-4 w-4" />
                <ChevronsRight v-else class="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {{ isCollapsed ? 'Expand sidebar' : 'Collapse sidebar' }}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Search -->
    <div v-if="!isCollapsed" class="px-3 pt-3 pb-1 relative">
      <div class="relative">
        <Search
          class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none"
        />
        <Input
          v-model="searchQuery"
          placeholder="Search resources..."
          class="h-8 pl-8 pr-3 text-sm bg-muted/50 border-transparent focus:border-border focus:bg-background"
          role="combobox"
          :aria-expanded="showDropdown"
          aria-controls="sidebar-search-results"
          aria-autocomplete="list"
          :aria-activedescendant="activeDescendantId"
          @focus="handleSearchFocus"
          @blur="handleSearchBlur"
          @keydown="handleSearchKeydown"
        />
      </div>
      <div
        v-if="showDropdown"
        id="sidebar-search-results"
        role="listbox"
        class="absolute left-3 right-3 top-full mt-1 bg-popover border border-border rounded-md shadow-md z-50 overflow-hidden"
      >
        <div v-if="searchResults.length === 0" class="px-3 py-2 text-xs text-muted-foreground">
          No results for "{{ searchQuery }}"
        </div>
        <button
          v-for="(result, index) in searchResults"
          :id="`sidebar-search-result-${index}`"
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
    <TooltipProvider v-else :delay-duration="0">
      <Tooltip>
        <TooltipTrigger as-child>
          <div class="px-2 pt-3 pb-1">
            <Button variant="ghost" size="icon" class="w-full h-9" @click="toggle">
              <Search class="h-4 w-4" />
            </Button>
          </div>
        </TooltipTrigger>
        <TooltipContent side="right">Search resources</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
      <!-- Main -->
      <template v-for="item in mainNav" :key="item.id">
        <TooltipProvider v-if="isCollapsed" :delay-duration="0">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
                size="icon"
                class="w-full h-9"
                :class="
                  renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''
                "
                @click="navigateTo(item.route)"
              >
                <component :is="item.icon" class="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">{{ item.label }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <Button
          v-else
          :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
          class="w-full justify-start h-9 px-3"
          :class="renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''"
          @click="navigateTo(item.route)"
        >
          <component :is="item.icon" class="h-5 w-5 mr-3 shrink-0" />
          <span class="truncate">{{ item.label }}</span>
        </Button>
      </template>

      <!-- Resources Section -->
      <div class="pt-4">
        <p
          v-if="!isCollapsed"
          class="px-3 pb-2 text-xs font-semibold text-muted-foreground tracking-wider uppercase"
        >
          Your Resources
        </p>
        <Separator v-else class="mb-2" />
        <div class="space-y-0.5">
          <template v-for="item in resourceNav" :key="item.id">
            <TooltipProvider v-if="isCollapsed" :delay-duration="0">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
                    size="icon"
                    class="w-full h-9"
                    :class="
                      renderNavItem(item).active
                        ? 'text-primary bg-primary/8 hover:bg-primary/12'
                        : ''
                    "
                    @click="navigateTo(item.route)"
                  >
                    <component :is="item.icon" class="h-5 w-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">{{ item.label }}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Button
              v-else
              :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
              class="w-full justify-start h-9 px-3"
              :class="
                renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''
              "
              @click="navigateTo(item.route)"
            >
              <component :is="item.icon" class="h-5 w-5 mr-3 shrink-0" />
              <span class="truncate">{{ item.label }}</span>
            </Button>
          </template>
        </div>
      </div>

      <!-- APIs Section -->
      <div class="pt-4">
        <div class="flex items-center justify-between" :class="isCollapsed ? '' : 'px-3 pb-2'">
          <p
            v-if="!isCollapsed"
            class="text-xs font-semibold text-muted-foreground tracking-wider uppercase"
          >
            APIs
          </p>
          <Separator v-if="isCollapsed" class="mb-2" />
          <TooltipProvider v-if="!isCollapsed" :delay-duration="0">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-5 w-5 text-muted-foreground hover:text-foreground"
                  @click="router.push({ name: 'go-live' })"
                >
                  <Plus class="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Publish</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <div class="space-y-0.5">
          <template v-for="item in liveNav" :key="item.id">
            <TooltipProvider v-if="isCollapsed" :delay-duration="0">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
                    size="icon"
                    class="w-full h-9 relative"
                    :class="
                      renderNavItem(item).active
                        ? 'text-primary bg-primary/8 hover:bg-primary/12'
                        : ''
                    "
                    @click="navigateTo(item.route)"
                  >
                    <component :is="item.icon" class="h-5 w-5" />
                    <Badge
                      v-if="renderNavItem(item).badgeValue"
                      :variant="item.badgeVariant ?? 'secondary'"
                      class="absolute -top-1 -right-1 h-5 min-w-[20px] flex items-center justify-center text-xs px-1"
                    >
                      {{ renderNavItem(item).badgeValue }}
                    </Badge>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {{ item.label }}
                  <template v-if="renderNavItem(item).badgeValue">
                    ({{ renderNavItem(item).badgeValue }})
                  </template>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Button
              v-else
              :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
              class="w-full justify-start h-9 px-3"
              :class="
                renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''
              "
              @click="navigateTo(item.route)"
            >
              <component :is="item.icon" class="h-5 w-5 mr-3 shrink-0" />
              <span class="truncate flex-1 text-left">{{ item.label }}</span>
              <Badge
                v-if="renderNavItem(item).badgeValue"
                :variant="item.badgeVariant ?? 'secondary'"
                class="ml-auto text-xs"
              >
                {{ renderNavItem(item).badgeValue }}
              </Badge>
            </Button>
          </template>
        </div>
      </div>
    </nav>

    <!-- Bottom Section -->
    <div class="mt-auto border-t border-border px-2 py-3 space-y-0.5">
      <!-- Inbox & Settings -->
      <template v-for="item in bottomNav" :key="item.id">
        <TooltipProvider v-if="isCollapsed" :delay-duration="0">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
                size="icon"
                class="w-full h-9 relative"
                :class="
                  renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''
                "
                @click="navigateTo(item.route)"
              >
                <component :is="item.icon" class="h-5 w-5" />
                <Badge
                  v-if="renderNavItem(item).badgeValue"
                  :variant="item.badgeVariant ?? 'secondary'"
                  class="absolute -top-1 -right-1 h-5 min-w-[20px] flex items-center justify-center text-xs px-1"
                >
                  {{ renderNavItem(item).badgeValue }}
                </Badge>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {{ item.label }}
              <template v-if="renderNavItem(item).badgeValue">
                ({{ renderNavItem(item).badgeValue }})
              </template>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <Button
          v-else
          :variant="renderNavItem(item).active ? 'secondary' : 'ghost'"
          class="w-full justify-start h-9 px-3"
          :class="renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''"
          @click="navigateTo(item.route)"
        >
          <component :is="item.icon" class="h-5 w-5 mr-3 shrink-0" />
          <span class="truncate flex-1 text-left">{{ item.label }}</span>
          <Badge
            v-if="renderNavItem(item).badgeValue"
            :variant="item.badgeVariant ?? 'secondary'"
            class="ml-auto text-xs"
          >
            {{ renderNavItem(item).badgeValue }}
          </Badge>
        </Button>
      </template>

      <Separator class="my-2" />

      <!-- User card -->
      <div
        class="flex items-center gap-3 rounded-lg p-2 hover:bg-muted transition-colors cursor-default"
        :class="isCollapsed ? 'justify-center' : ''"
      >
        <Avatar class="h-8 w-8 shrink-0">
          <AvatarFallback class="bg-muted text-muted-foreground text-xs">
            <User class="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
        <div v-if="!isCollapsed" class="min-w-0 flex-1">
          <p class="text-sm font-medium text-foreground truncate">
            {{ userStore.email || 'Not connected' }}
          </p>
        </div>
      </div>
    </div>
  </aside>
</template>
