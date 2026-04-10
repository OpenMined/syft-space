<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
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
  Wallet,
  Plus,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Separator } from '@/components/ui/separator'
import { useSidebar } from '@/composables/useSidebar'
import { useInboxStore } from '@/stores/inbox'
import { useUserStore } from '@/stores/user'
import { useEndpointsStore } from '@/stores/endpoints'
import SyftLogo from '@/assets/syftbox-logo.svg'
import ThemeToggle from '@/components/ThemeToggle.vue'

const router = useRouter()
const route = useRoute()
const { isCollapsed, toggle } = useSidebar()
const inboxStore = useInboxStore()
const userStore = useUserStore()
const endpointsStore = useEndpointsStore()

const liveCount = computed(() => endpointsStore.endpoints.filter((e) => e.published).length)

const routeMapping: Record<string, string[]> = {
  home: ['home'],
  datasets: ['datasets', 'dataset-detail'],
  models: ['models', 'model-detail'],
  endpoints: ['endpoints', 'endpoint-detail'],
  inbox: ['inbox'],
  analytics: ['analytics'],
  settings: ['settings'],
}

const isActive = (navId: string) => {
  const routes = routeMapping[navId]
  return routes ? routes.includes(route.name as string) : false
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
    <div class="flex items-center h-16 px-4 border-b border-border shrink-0">
      <button class="flex items-center gap-3 min-w-0" @click="navigateTo('home')">
        <img :src="SyftLogo" alt="Syft Space" class="h-7 w-7 shrink-0" />
        <span
          v-if="!isCollapsed"
          class="text-sm font-semibold text-foreground tracking-tight truncate"
        >
          Syft Space
        </span>
      </button>
    </div>

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
          :class="
            renderNavItem(item).active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''
          "
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

      <Separator class="my-2" />

      <!-- Theme + Collapse toggle row -->
      <div
        class="flex items-center"
        :class="isCollapsed ? 'justify-center' : 'justify-between px-1'"
      >
        <ThemeToggle />
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
          <div class="flex items-center gap-1.5">
            <Wallet class="h-3 w-3 text-muted-foreground shrink-0" />
            <span class="text-xs text-muted-foreground truncate">
              {{ userStore.formattedBalance() }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
