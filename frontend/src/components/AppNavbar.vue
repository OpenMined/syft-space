<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, ExternalLink, Settings } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useUserStore } from '@/stores/user'
import { useInboxStore } from '@/stores/inbox'
import ThemeToggle from '@/components/ThemeToggle.vue'
import SyftLogo from '@/assets/syftbox-logo.svg'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const inboxStore = useInboxStore()

const currentRouteName = computed(() => route.name as string)

const routeMapping: Record<string, string[]> = {
  endpoints: ['endpoints', 'endpoint-detail'],
  datasets: ['datasets', 'dataset-detail'],
  models: ['models', 'model-detail'],
}

const isTabActive = (tabId: string) => {
  const routes = routeMapping[tabId]
  return routes ? routes.includes(currentRouteName.value) : currentRouteName.value === tabId
}

const navigateTo = (routeName: string) => {
  router.push({ name: routeName })
}

const tabs = [
  { id: 'home', label: 'Home' },
  { id: 'datasets', label: 'Datasets' },
  { id: 'models', label: 'Models' },
  { id: 'endpoints', label: 'Endpoints' },
  { id: 'earnings', label: 'Earnings' },
]
</script>

<template>
  <header class="bg-background shadow-sm border-b border-border">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-16 gap-6">
      <!-- Logo and App Name -->
      <div class="flex items-center space-x-3">
        <img :src="SyftLogo" alt="Syft Space" class="h-8 w-8" />
        <span class="text-lg font-bold text-foreground tracking-tight">
          Syft Space
          <span class="ml-1 text-xs font-semibold text-primary align-top">BETA</span>
        </span>
      </div>

      <!-- Navigation Tabs -->
      <nav class="flex items-center space-x-2 flex-grow justify-center">
        <div v-for="tab in tabs" :key="tab.id" class="relative">
          <Button
            @click="navigateTo(tab.id)"
            :variant="isTabActive(tab.id) ? 'secondary' : 'ghost'"
            size="sm"
            class="text-sm font-medium"
            :class="[
              isTabActive(tab.id)
                ? 'text-primary bg-primary/10 hover:bg-primary/20'
                : 'text-foreground hover:bg-muted',
            ]"
          >
            {{ tab.label }}
          </Button>
          <Badge
            v-if="tab.id === 'inbox' && inboxStore.unreadCount > 0"
            variant="destructive"
            class="absolute -top-2 -right-2 h-5 w-5 flex items-center justify-center text-xs font-semibold min-w-[20px] rounded-full border-2 border-background"
          >
            {{ inboxStore.unreadCount > 9 ? '9+' : inboxStore.unreadCount }}
          </Badge>
        </div>
      </nav>

      <!-- Right side controls -->
      <div class="flex items-center space-x-3">
        <!-- Theme Toggle -->
        <ThemeToggle />

        <!-- Avatar with Dropdown -->
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <Button variant="ghost" size="icon" class="h-10 w-10 rounded-lg">
              <Avatar class="h-8 w-8">
                <AvatarFallback class="bg-muted text-muted-foreground">
                  <User class="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent class="w-56" align="end">
            <div class="p-4 space-y-4">
              <!-- Loading skeleton -->
              <template v-if="userStore.marketplaceLoading">
                <div class="space-y-1.5">
                  <Skeleton class="h-3 w-10" />
                  <Skeleton class="h-4 w-32" />
                </div>
                <div class="space-y-1.5">
                  <Skeleton class="h-3 w-16" />
                  <Skeleton class="h-4 w-36" />
                </div>
              </template>
              <!-- Loaded content -->
              <template v-else>
                <div>
                  <p class="text-sm text-muted-foreground mb-0.5">Email</p>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <p class="text-sm font-medium text-foreground truncate cursor-default">
                          {{ userStore.email || '--' }}
                        </p>
                      </TooltipTrigger>
                      <TooltipContent v-if="userStore.email">
                        <p>{{ userStore.email }}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div>
                  <p class="text-sm text-muted-foreground mb-0.5">Marketplace</p>
                  <a
                    v-if="userStore.marketplaceUrl"
                    :href="userStore.marketplaceUrl"
                    target="_blank"
                    class="text-sm font-medium text-foreground hover:text-muted-foreground inline-flex items-center gap-1.5"
                  >
                    {{ userStore.marketplaceUrl.replace('https://', '').replace(/\/$/, '') }}
                    <ExternalLink class="h-3 w-3 text-muted-foreground" />
                  </a>
                  <p v-else class="text-sm font-medium text-foreground">--</p>
                </div>
              </template>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem @click="navigateTo('settings')" class="cursor-pointer">
              <Settings class="h-4 w-4 mr-2" />
              Settings
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  </header>
</template>
