<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  User,
  ExternalLink,
  Settings,
  ChevronUp,
  RefreshCw,
  CircleAlert,
  ArrowDownLeft,
} from 'lucide-vue-next'
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useUserStore } from '@/stores/user'
import { useInboxStore } from '@/stores/inbox'
import { formatPrice } from '@/lib/formatters'
import ThemeToggle from '@/components/ThemeToggle.vue'
import TransactionsDialog from '@/components/TransactionsDialog.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const inboxStore = useInboxStore()

const balanceDropdownOpen = ref(false)
const isRefreshing = ref(false)
const transactionsDialogOpen = ref(false)

// Auto-refresh balance every 30 seconds
let balanceRefreshInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  balanceRefreshInterval = setInterval(() => {
    userStore.fetchBalance(true)
  }, 30000)
})

onUnmounted(() => {
  if (balanceRefreshInterval) {
    clearInterval(balanceRefreshInterval)
  }
})

const formatTimeAgo = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

const truncateEmail = (email: string): string => {
  const [local, domain] = email.split('@')
  if (!local || !domain) return email
  const truncatedLocal = local.length > 6 ? `${local.slice(0, 6)}...` : local
  return `${truncatedLocal}@${domain}`
}

const isLowBalance = computed(() => {
  return userStore.balance !== null && userStore.balance > 0 && userStore.balance <= 20
})

const isZeroBalance = computed(() => {
  return userStore.balance !== null && userStore.balance === 0
})

const balanceIndicatorColor = computed(() => {
  if (userStore.balance === 0) return 'bg-red-500'
  if (userStore.balance !== null && userStore.balance <= 20) return 'bg-amber-500'
  return ''
})

const formattedBalanceNumber = computed(() => {
  if (userStore.balance === null) return '--'
  return formatPrice(userStore.balance)
})

const refreshBalance = async () => {
  isRefreshing.value = true
  await userStore.fetchBalance()
  isRefreshing.value = false
}

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
]
</script>

<template>
  <header class="bg-background shadow-sm border-b border-border">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-16 gap-6">
      <!-- Logo and App Name -->
      <div class="flex items-center space-x-3">
        <div
          class="h-8 w-8 bg-gradient-to-br from-primary to-primary/80 rounded-lg flex items-center justify-center"
        >
          <span class="text-primary-foreground font-bold text-base">S</span>
        </div>
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
        <!-- Balance Dropdown -->
        <DropdownMenu v-model:open="balanceDropdownOpen">
          <DropdownMenuTrigger as-child>
            <Button variant="outline" size="sm" class="flex items-center gap-2 px-3 py-1.5 h-auto">
              <span class="text-sm text-muted-foreground">Balance:</span>
              <!-- Loading state -->
              <template v-if="userStore.balanceLoading">
                <RefreshCw class="h-4 w-4 text-muted-foreground animate-spin" />
              </template>
              <!-- Error state -->
              <template v-else-if="userStore.balanceError">
                <CircleAlert class="h-4 w-4 text-red-500" />
                <span class="text-sm font-semibold text-red-500">Error</span>
              </template>
              <!-- Normal state -->
              <template v-else>
                <span
                  v-if="isLowBalance || isZeroBalance"
                  class="h-2.5 w-2.5 rounded-full"
                  :class="balanceIndicatorColor"
                ></span>
                <span class="text-sm font-semibold">${{ formattedBalanceNumber }}</span>
              </template>
              <ChevronUp
                class="h-4 w-4 text-muted-foreground transition-transform duration-200"
                :class="{ 'rotate-180': !balanceDropdownOpen }"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent class="w-80" align="end">
            <!-- Header -->
            <div class="flex items-center justify-between px-4 pt-4 pb-2">
              <span class="text-xs font-semibold text-muted-foreground tracking-wide"
                >AVAILABLE CREDITS</span
              >
              <Button
                variant="ghost"
                size="icon"
                class="h-6 w-6"
                @click.stop="refreshBalance"
                :disabled="isRefreshing"
              >
                <RefreshCw
                  class="h-4 w-4 text-muted-foreground"
                  :class="{ 'animate-spin': isRefreshing }"
                />
              </Button>
            </div>

            <!-- Balance Display -->
            <div class="px-4 pb-3">
              <!-- Error state -->
              <div v-if="userStore.balanceError" class="flex items-center gap-2">
                <CircleAlert class="h-5 w-5 text-red-500" />
                <span class="text-base font-medium text-red-500">Failed to load balance</span>
              </div>
              <!-- Loading state -->
              <div v-else-if="userStore.balanceLoading">
                <Skeleton class="h-8 w-32" />
              </div>
              <!-- Normal state -->
              <div v-else class="flex items-center gap-2">
                <span
                  v-if="isLowBalance || isZeroBalance"
                  class="h-3 w-3 rounded-full"
                  :class="balanceIndicatorColor"
                ></span>
                <span class="text-3xl font-bold">${{ formattedBalanceNumber }}</span>
                <span class="text-lg text-muted-foreground">{{ userStore.currency }}</span>
              </div>
            </div>

            <!-- Low Balance Warning -->
            <div
              v-if="isLowBalance && !userStore.balanceLoading && !userStore.balanceError"
              class="px-4 pb-3"
            >
              <Alert
                class="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/50"
              >
                <AlertDescription class="text-amber-700 dark:text-amber-400 text-sm">
                  Your balance is running low. Consider adding more credits.
                </AlertDescription>
              </Alert>
            </div>

            <!-- Zero Balance Warning -->
            <div
              v-if="isZeroBalance && !userStore.balanceLoading && !userStore.balanceError"
              class="px-4 pb-3"
            >
              <Alert class="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/50">
                <AlertDescription class="text-red-700 dark:text-red-400 text-sm">
                  Your balance is empty. Add credits to continue using services.
                </AlertDescription>
              </Alert>
            </div>

            <!-- Recent Activity Section -->
            <div class="px-4 py-3 border-t border-border">
              <h4 class="text-sm font-medium mb-3">Recent Transactions</h4>
              <div class="space-y-3">
                <!-- Loading state -->
                <template v-if="userStore.balanceLoading">
                  <div v-for="i in 3" :key="i" class="flex items-center gap-3">
                    <Skeleton class="h-10 w-10 rounded-full" />
                    <div class="flex-1 space-y-1.5">
                      <Skeleton class="h-4 w-32" />
                      <Skeleton class="h-3 w-20" />
                    </div>
                    <Skeleton class="h-4 w-12" />
                  </div>
                </template>
                <!-- Transaction list -->
                <template v-else-if="userStore.transactions.length > 0">
                  <div
                    v-for="transaction in userStore.transactions"
                    :key="transaction.id"
                    class="flex items-center gap-3"
                  >
                    <div
                      class="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center"
                    >
                      <ArrowDownLeft class="h-4 w-4 text-green-600 dark:text-green-400" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <p class="text-sm font-medium truncate cursor-default">
                              From {{ truncateEmail(transaction.sender_email) }}
                            </p>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{{ transaction.sender_email }}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <span class="text-xs text-muted-foreground cursor-default">
                              {{ formatTimeAgo(transaction.created_at) }}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{{ new Date(transaction.created_at).toLocaleString() }}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <span class="text-sm font-semibold text-green-600 dark:text-green-400">
                      +${{ formatPrice(transaction.amount) }}
                    </span>
                  </div>
                </template>
                <!-- Empty state -->
                <p v-else class="text-sm text-muted-foreground text-center py-4">
                  No recent activity
                </p>
              </div>
            </div>

            <DropdownMenuSeparator />

            <!-- Footer Actions -->
            <div class="p-2">
              <Button
                variant="default"
                size="sm"
                class="w-full"
                @click="transactionsDialogOpen = true; balanceDropdownOpen = false"
              >
                View All
              </Button>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        <!-- Transactions Dialog -->
        <TransactionsDialog v-model:open="transactionsDialogOpen" />

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
