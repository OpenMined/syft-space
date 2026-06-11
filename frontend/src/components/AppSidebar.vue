<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Database,
  Brain,
  Globe,
  Settings,
  User,
  Plus,
  MessageSquare,
  BarChart3,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Separator } from '@/components/ui/separator'
import { useSidebar } from '@/composables/useSidebar'
import { useUserStore } from '@/stores/user'
import { useEndpointsStore } from '@/stores/endpoints'
import SyftLogo from '@/assets/syftbox-logo.svg'
import SidebarNavItem from '@/components/SidebarNavItem.vue'

const router = useRouter()
const route = useRoute()
const { isCollapsed, toggle } = useSidebar()
const userStore = useUserStore()
const endpointsStore = useEndpointsStore()

const liveCount = computed(() => endpointsStore.endpoints.filter((e) => e.published).length)

const routeMapping: Record<string, string[]> = {
  home: ['home'],
  datasets: ['datasets', 'dataset-detail'],
  models: ['models', 'model-detail'],
  chat: ['chat'],
  endpoints: ['endpoints', 'endpoint-detail'],
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
  { id: 'analytics', route: 'analytics', label: 'Analytics', icon: BarChart3 },
]

const bottomNav: NavItem[] = []

interface ResolvedNavItem extends NavItem {
  active: boolean
  badgeValue: number | string | undefined
}

const resolveNav = (items: NavItem[]): ResolvedNavItem[] =>
  items.map((item) => ({
    ...item,
    active: isActive(item.id),
    badgeValue: item.badge?.(),
  }))

const mainNavResolved = computed(() => resolveNav(mainNav))
const resourceNavResolved = computed(() => resolveNav(resourceNav))
const liveNavResolved = computed(() => resolveNav(liveNav))
const bottomNavResolved = computed(() => resolveNav(bottomNav))
</script>

<template>
  <aside
    class="flex flex-col h-full bg-background border-r border-border/40 transition-all duration-200 ease-in-out"
    :class="isCollapsed ? 'w-16' : 'w-60'"
  >
    <!-- Logo -->
    <div class="flex items-center justify-between h-16 px-4 shrink-0">
      <TooltipProvider :delay-duration="0">
        <Tooltip>
          <TooltipTrigger as-child>
            <button class="flex items-center gap-3 min-w-0" @click="toggle">
              <img :src="SyftLogo" alt="Syft Space" class="h-7 w-7 shrink-0" />
              <span
                v-if="!isCollapsed"
                class="text-sm font-semibold text-foreground tracking-tight truncate"
              >
                Syft Space
              </span>
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {{ isCollapsed ? 'Expand sidebar' : 'Collapse sidebar' }}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
      <SidebarNavItem
        v-for="item in mainNavResolved"
        :key="item.id"
        :item="item"
        :collapsed="isCollapsed"
        @click="navigateTo(item.route)"
      />

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
          <SidebarNavItem
            v-for="item in resourceNavResolved"
            :key="item.id"
            :item="item"
            :collapsed="isCollapsed"
            @click="navigateTo(item.route)"
          />
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
          <SidebarNavItem
            v-for="item in liveNavResolved"
            :key="item.id"
            :item="item"
            :collapsed="isCollapsed"
            @click="navigateTo(item.route)"
          />
        </div>
      </div>
    </nav>

    <!-- Bottom Section -->
    <div class="mt-auto border-t border-border px-2 py-3 space-y-0.5">
      <SidebarNavItem
        v-for="item in bottomNavResolved"
        :key="item.id"
        :item="item"
        :collapsed="isCollapsed"
        @click="navigateTo(item.route)"
      />

      <!-- User card + Settings -->
      <div class="flex items-center gap-2 rounded-lg p-2" :class="isCollapsed ? 'flex-col' : ''">
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
        <TooltipProvider :delay-duration="0">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                :variant="isActive('settings') ? 'secondary' : 'ghost'"
                size="icon"
                class="h-8 w-8 shrink-0"
                :class="isActive('settings') ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''"
                @click="navigateTo('settings')"
              >
                <Settings class="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent :side="isCollapsed ? 'right' : 'top'"> Settings </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  </aside>
</template>
