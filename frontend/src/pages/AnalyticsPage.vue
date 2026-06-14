<template>
  <div
    :class="[
      'mx-auto px-4 sm:px-6 lg:px-8',
      isCollectiveViewActive ? 'max-w-5xl py-12 lg:py-16' : 'max-w-7xl py-8 lg:py-12',
    ]"
  >
    <div :class="isCollectiveViewActive ? 'mb-12' : 'mb-10'">
      <div class="flex items-center gap-3 mb-3">
        <BarChart3 class="h-6 w-6 text-primary" />
        <h1
          :class="
            isCollectiveViewActive
              ? 'text-2xl font-semibold tracking-tight text-foreground'
              : 'heading-3'
          "
        >
          {{ isCollectiveViewActive ? 'Collective Stats' : 'Analytics' }}
        </h1>
      </div>
      <p class="body-lg text-muted-foreground">
        {{
          isCollectiveViewActive
            ? 'Revenue and usage across members querying your collective APIs.'
            : 'Aggregated analytics across your APIs'
        }}
      </p>
    </div>

    <template v-if="isCollectiveViewActive">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Total collective revenue</p>
            <DollarSign class="w-4 h-4 text-green-500 dark:text-green-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">
            {{ formatCurrency(collectiveStatsSummary.totalRevenue) }}
          </p>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Revenue this month</p>
            <TrendingUp class="w-4 h-4 text-green-500 dark:text-green-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">
            {{ formatCurrency(collectiveStatsSummary.monthlyRevenue) }}
          </p>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Members active</p>
            <UsersRound class="w-4 h-4 text-blue-500 dark:text-blue-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">
            {{ collectiveStatsSummary.activeMembers }}/{{ collectiveStatsSummary.totalMembers }}
          </p>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Earning members</p>
            <Activity class="w-4 h-4 text-primary" />
          </div>
          <p class="text-3xl font-bold text-foreground">
            {{ collectiveStatsSummary.earningMembers }}/{{ collectiveStatsSummary.totalMembers }}
          </p>
        </div>
      </div>

      <div class="space-y-6">
        <div class="bg-card rounded-lg p-6 border border-border">
          <h2 class="text-lg font-medium text-foreground mb-1">Revenue by date</h2>
          <p class="body-sm text-muted-foreground mb-6">Daily revenue across all collective APIs.</p>
          <div class="flex gap-2 h-52">
            <div
              v-for="point in revenueByDate"
              :key="point.date"
              class="flex-1 flex flex-col min-w-0 h-full"
            >
              <div class="flex-1 flex items-end min-h-0">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <div
                        class="w-full rounded-t-md bg-primary/80 hover:bg-primary transition-colors cursor-default"
                        :style="{
                          height: `${barHeightPx(point.revenue, maxDailyRevenue)}px`,
                        }"
                      />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{{ point.label }}: {{ formatCurrency(point.revenue) }}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <span
                class="text-[10px] text-muted-foreground truncate w-full text-center mt-2 shrink-0"
              >
                {{ point.label }}
              </span>
            </div>
          </div>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h2 class="text-lg font-medium text-foreground mb-1">Revenue by collective API</h2>
              <p class="body-sm text-muted-foreground">
                Earnings from collective APIs hosted by members.
              </p>
            </div>
            <div class="relative w-full sm:max-w-xs">
              <Search
                class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              />
              <Input
                v-model="endpointRevenueSearch"
                placeholder="Search collective APIs..."
                class="pl-9"
              />
            </div>
          </div>
          <div
            v-if="filteredRevenueEndpoints.length === 0"
            class="text-sm text-muted-foreground py-6 text-center"
          >
            No collective APIs match "{{ endpointRevenueSearch }}"
          </div>
          <div v-else class="space-y-4">
            <div v-for="endpoint in filteredRevenueEndpoints" :key="endpoint.name" class="space-y-2">
              <div class="flex items-center justify-between gap-4">
                <div class="min-w-0">
                  <p class="text-sm font-medium truncate font-mono">{{ endpoint.name }}</p>
                  <p class="text-xs text-muted-foreground truncate">{{ endpoint.detail }}</p>
                </div>
                <p class="text-sm font-semibold shrink-0">{{ formatCurrency(endpoint.revenue) }}</p>
              </div>
              <div class="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  class="h-full rounded-full bg-primary/70"
                  :style="{ width: `${barWidth(endpoint.revenue, maxEndpointRevenue)}%` }"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h2 class="text-lg font-medium text-foreground mb-1">Revenue by member</h2>
              <p class="body-sm text-muted-foreground">Members generating revenue through collective APIs.</p>
            </div>
            <div class="relative w-full sm:max-w-xs">
              <Search
                class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              />
              <Input
                v-model="revenueMemberSearch"
                placeholder="Search members..."
                class="pl-9"
              />
            </div>
          </div>
          <div v-if="filteredRevenueMembers.length === 0" class="text-sm text-muted-foreground py-6 text-center">
            No members match "{{ revenueMemberSearch }}"
          </div>
          <div v-else class="space-y-4">
            <div v-for="member in filteredRevenueMembers" :key="member.id" class="space-y-2">
              <div class="flex items-center justify-between gap-4">
                <div class="min-w-0">
                  <p class="text-sm font-medium truncate">{{ member.name }}</p>
                  <p class="text-xs text-muted-foreground truncate">{{ member.email }}</p>
                </div>
                <p class="text-sm font-semibold shrink-0">{{ formatCurrency(member.revenue) }}</p>
              </div>
              <div class="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  class="h-full rounded-full bg-primary"
                  :style="{ width: `${barWidth(member.revenue, maxMemberRevenue)}%` }"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h2 class="text-lg font-medium text-foreground mb-1">Requests by member</h2>
              <p class="body-sm text-muted-foreground">Query volume across collective APIs.</p>
            </div>
            <div class="relative w-full sm:max-w-xs">
              <Search
                class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              />
              <Input
                v-model="requestsMemberSearch"
                placeholder="Search members..."
                class="pl-9"
              />
            </div>
          </div>
          <div v-if="filteredRequestMembers.length === 0" class="text-sm text-muted-foreground py-6 text-center">
            No members match "{{ requestsMemberSearch }}"
          </div>
          <div v-else class="space-y-4">
            <div v-for="member in filteredRequestMembers" :key="member.id" class="space-y-2">
              <div class="flex items-center justify-between gap-4">
                <div class="min-w-0">
                  <p class="text-sm font-medium truncate">{{ member.name }}</p>
                  <p class="text-xs text-muted-foreground truncate">{{ member.email }}</p>
                </div>
                <p class="text-sm font-semibold shrink-0">{{ formatNumber(member.requests) }}</p>
              </div>
              <div class="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  class="h-full rounded-full bg-primary/80"
                  :style="{ width: `${barWidth(member.requests, maxMemberRequests)}%` }"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div v-if="isCollectiveMember" class="flex flex-wrap items-center gap-3 mb-6">
        <span class="body-sm font-medium text-muted-foreground">Filter by source</span>
        <Select v-model="querySourceFilter">
          <SelectTrigger class="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All queries</SelectItem>
            <SelectItem value="collective">Via {{ collectiveName }}</SelectItem>
            <SelectItem value="direct">Direct queries</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Active</p>
            <CheckCircle class="w-4 h-4 text-green-500 dark:text-green-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">{{ activeCount }}</p>
          <p class="body-sm text-green-600 dark:text-green-400 mt-2">+2 from last week</p>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">{{ queriesLabel }}</p>
            <Activity class="w-4 h-4 text-blue-500 dark:text-blue-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">{{ displayAnalytics.totalRequests }}</p>
          <p class="body-sm text-blue-600 dark:text-blue-400 mt-2">↑ 12% from yesterday</p>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Revenue</p>
            <DollarSign class="w-4 h-4 text-green-500 dark:text-green-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">{{ displayAnalytics.totalEarnings }}</p>
          <p class="body-sm text-green-600 dark:text-green-400 mt-2">
            ↑ {{ displayAnalytics.monthlyEarnings }} this month
          </p>
        </div>

        <div class="bg-card rounded-lg p-6 border border-border">
          <div class="flex items-center justify-between mb-2">
            <p class="body-sm font-medium text-muted-foreground">Success Rate</p>
            <TrendingUp class="w-4 h-4 text-green-500 dark:text-green-400" />
          </div>
          <p class="text-3xl font-bold text-foreground">{{ analytics.successRate }}</p>
          <p class="body-sm text-muted-foreground mt-2">Last 24 hours</p>
        </div>
      </div>

      <div class="bg-card rounded-lg p-8 border border-border text-center text-muted-foreground">
        More detailed charts and breakdowns coming soon.
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  CheckCircle,
  Activity,
  DollarSign,
  TrendingUp,
  BarChart3,
  UsersRound,
  Search,
} from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useEndpointsStore } from '@/stores/endpoints'
import { getMockAnalytics } from '@/stores/mockData'
import {
  collectiveStatsSummary,
  revenueByDate,
  memberUsageStats,
  collectiveApiStats,
} from '@/stores/mockCollective'
import { useCollectiveMode } from '@/composables/useCollectiveMode'

const endpointsStore = useEndpointsStore()
const { isCollectiveViewActive, isCollectiveMember } = useCollectiveMode()
const collectiveName = collectiveStatsSummary.name

const revenueMemberSearch = ref('')
const requestsMemberSearch = ref('')
const endpointRevenueSearch = ref('')

const activeCount = computed(() => endpointsStore.endpoints.filter((e) => e.published).length)
const analytics = getMockAnalytics('endpoint')

// Member stats: split personal usage by query source (collective vs direct).
// Illustrative mock numbers that add up to the "all" totals. Demo UI only.
type QuerySource = 'all' | 'collective' | 'direct'
const querySourceFilter = ref<QuerySource>('all')

const analyticsBySource: Record<
  QuerySource,
  { totalRequests: string; totalEarnings: string; monthlyEarnings: string }
> = {
  all: {
    totalRequests: analytics.totalRequests,
    totalEarnings: analytics.totalEarnings,
    monthlyEarnings: analytics.monthlyEarnings,
  },
  collective: { totalRequests: '31.4k', totalEarnings: '$1,488.20', monthlyEarnings: '$402.10' },
  direct: { totalRequests: '13.8k', totalEarnings: '$657.40', monthlyEarnings: '$165.10' },
}

const displayAnalytics = computed(() =>
  isCollectiveMember.value ? analyticsBySource[querySourceFilter.value] : analyticsBySource.all,
)

const queriesLabel = computed(() =>
  querySourceFilter.value === 'collective' && isCollectiveMember.value
    ? 'Collective Queries'
    : querySourceFilter.value === 'direct' && isCollectiveMember.value
      ? 'Direct Queries'
      : 'Total Queries',
)

const maxDailyRevenue = computed(() => Math.max(...revenueByDate.map((d) => d.revenue), 1))
const maxEndpointRevenue = computed(() =>
  Math.max(...collectiveApiStats.map((e) => e.revenue), 1),
)
const maxMemberRevenue = computed(() => Math.max(...memberUsageStats.map((m) => m.revenue), 1))
const maxMemberRequests = computed(() => Math.max(...memberUsageStats.map((m) => m.requests), 1))

const filterEndpoints = (query: string) => {
  const q = query.toLowerCase().trim()
  if (!q) return collectiveApiStats
  return collectiveApiStats.filter(
    (e) => e.name.toLowerCase().includes(q) || e.detail.toLowerCase().includes(q),
  )
}

const filteredRevenueEndpoints = computed(() =>
  [...filterEndpoints(endpointRevenueSearch.value)].sort((a, b) => b.revenue - a.revenue),
)

const filterMembers = (query: string) => {
  const q = query.toLowerCase().trim()
  if (!q) return memberUsageStats
  return memberUsageStats.filter(
    (m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q),
  )
}

const filteredRevenueMembers = computed(() =>
  [...filterMembers(revenueMemberSearch.value)].sort((a, b) => b.revenue - a.revenue),
)

const filteredRequestMembers = computed(() =>
  [...filterMembers(requestsMemberSearch.value)].sort((a, b) => b.requests - a.requests),
)

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)

const CHART_BAR_MAX_PX = 160

const barHeightPx = (value: number, max: number) =>
  Math.max(6, Math.round((value / max) * CHART_BAR_MAX_PX))

const barWidth = (value: number, max: number) => (max === 0 ? 0 : (value / max) * 100)
</script>
