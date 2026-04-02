<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-2">
            <BarChart3 class="h-6 w-6 text-primary" />
            <h1 class="heading-3">Analytics</h1>
          </div>
          <p class="body-lg text-muted-foreground">
            Comprehensive analytics across your endpoints, users, and revenue
          </p>
        </div>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="outline"
                :disabled="!store.hasData"
                class="gap-2"
                @click="store.exportData()"
              >
                <Download class="h-4 w-4" />
                Export All Data
              </Button>
            </TooltipTrigger>
            <TooltipContent v-if="!store.hasData">No data to export</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Filters -->
    <Card class="mb-6">
      <CardContent class="px-6 py-4">
        <div class="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div class="flex items-center gap-2 text-sm font-medium text-foreground">
            <Filter class="h-4 w-4" />
            Filters
          </div>
          <div class="flex flex-wrap items-center gap-4">
            <div class="flex items-center gap-2">
              <span class="text-sm text-muted-foreground">Time Range:</span>
              <Select v-model="store.timeRange">
                <SelectTrigger class="w-[150px] h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="opt in timeRangeOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-sm text-muted-foreground">Endpoint:</span>
              <Select v-model="selectedEndpointId">
                <SelectTrigger class="w-[170px] h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem :value="ALL_SENTINEL">All Endpoints</SelectItem>
                  <SelectItem v-for="ep in endpointsList" :key="ep.id" :value="ep.id">
                    {{ ep.name }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
        </div>
      </CardContent>
    </Card>

    <!-- Stat Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <template v-if="store.summaryLoading">
        <Card v-for="i in 4" :key="`stat-skeleton-${i}`">
          <CardContent class="p-5">
            <div class="animate-pulse">
              <div class="h-3 bg-muted rounded w-1/2 mb-4" />
              <div class="h-8 bg-muted rounded w-2/3 mb-2" />
              <div class="h-3 bg-muted rounded w-3/4" />
            </div>
          </CardContent>
        </Card>
      </template>
      <template v-else-if="store.summaryError">
        <Card class="col-span-full">
          <CardContent class="p-5 text-center">
            <p class="text-destructive mb-2">{{ store.summaryError }}</p>
            <Button variant="outline" size="sm" @click="store.fetchSummary()"> Retry </Button>
          </CardContent>
        </Card>
      </template>
      <template v-else>
        <Card v-for="stat in statCards" :key="stat.label" class="transition-shadow hover:shadow-md">
          <CardContent class="p-5">
            <div class="flex items-center justify-between mb-3">
              <p class="text-sm font-medium text-muted-foreground">{{ stat.label }}</p>
              <div class="w-8 h-8 rounded-lg flex items-center justify-center" :class="stat.iconBg">
                <component :is="stat.iconComponent" class="w-4 h-4" :class="stat.iconFg" />
              </div>
            </div>
            <p class="text-3xl font-bold text-foreground tracking-tight tabular-nums">
              {{ stat.formattedValue }}
            </p>
            <p
              class="text-xs mt-1.5"
              :class="
                stat.changePositive ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'
              "
            >
              {{ stat.changeLabel }}
            </p>
          </CardContent>
        </Card>
      </template>
    </div>

    <!-- Charts Row 1 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <!-- Query Volume Trends -->
      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <TrendingUp class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">Query Volume Trends</span>
          </div>
          <p class="text-xs text-muted-foreground mb-5">Query count over time</p>
          <div class="h-52">
            <template v-if="store.timeSeriesLoading">
              <div class="animate-pulse h-full bg-muted rounded" />
            </template>
            <template v-else-if="store.timeSeriesError">
              <div class="flex items-center justify-center h-full">
                <div class="text-center">
                  <p class="text-sm text-destructive mb-2">Failed to load chart</p>
                  <Button variant="outline" size="sm" @click="store.fetchTimeSeries()">
                    Retry
                  </Button>
                </div>
              </div>
            </template>
            <template v-else-if="isQueryVolumeEmpty">
              <div class="flex items-center justify-center h-full">
                <p class="text-sm text-muted-foreground">No query data for this period</p>
              </div>
            </template>
            <template v-else>
              <Line :data="queryVolumeChartData" :options="lineChartOptions" />
            </template>
          </div>
        </CardContent>
      </Card>

      <!-- User Activity -->
      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <UsersRound class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">User Activity</span>
          </div>
          <p class="text-xs text-muted-foreground mb-5">Distinct active users</p>
          <div class="h-52">
            <template v-if="store.timeSeriesLoading">
              <div class="animate-pulse h-full bg-muted rounded" />
            </template>
            <template v-else-if="store.timeSeriesError">
              <div class="flex items-center justify-center h-full">
                <div class="text-center">
                  <p class="text-sm text-destructive mb-2">Failed to load chart</p>
                  <Button variant="outline" size="sm" @click="store.fetchTimeSeries()">
                    Retry
                  </Button>
                </div>
              </div>
            </template>
            <template v-else-if="isUserActivityEmpty">
              <div class="flex items-center justify-center h-full">
                <p class="text-sm text-muted-foreground">No activity data for this period</p>
              </div>
            </template>
            <template v-else>
              <Bar :data="userActivityChartData" :options="barChartOptions" />
            </template>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Charts Row 2 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- Revenue Overview -->
      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <DollarSign class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">Revenue Overview</span>
          </div>
          <p class="text-xs text-muted-foreground mb-5">Revenue over time</p>
          <div class="h-52">
            <template v-if="store.timeSeriesLoading">
              <div class="animate-pulse h-full bg-muted rounded" />
            </template>
            <template v-else-if="store.timeSeriesError">
              <div class="flex items-center justify-center h-full">
                <div class="text-center">
                  <p class="text-sm text-destructive mb-2">Failed to load chart</p>
                  <Button variant="outline" size="sm" @click="store.fetchTimeSeries()">
                    Retry
                  </Button>
                </div>
              </div>
            </template>
            <template v-else-if="isRevenueEmpty">
              <div class="flex items-center justify-center h-full">
                <p class="text-sm text-muted-foreground">No revenue data for this period</p>
              </div>
            </template>
            <template v-else>
              <Line :data="revenueChartData" :options="revenueChartOptions" />
            </template>
          </div>
        </CardContent>
      </Card>

      <!-- Most Active Users -->
      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <Heart class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">Most Active Users</span>
          </div>
          <p class="text-xs text-muted-foreground mb-4">Top users by query volume</p>
          <template v-if="store.topUsersLoading">
            <div class="space-y-3">
              <div
                v-for="i in 5"
                :key="`user-skeleton-${i}`"
                class="animate-pulse flex items-center gap-3 px-3 py-2.5"
              >
                <div class="w-6 h-6 rounded-full bg-muted shrink-0" />
                <div class="flex-1">
                  <div class="h-3 bg-muted rounded w-1/3 mb-2" />
                  <div class="h-1.5 bg-muted rounded w-full" />
                </div>
              </div>
            </div>
          </template>
          <template v-else-if="store.topUsersError">
            <div class="text-center py-4">
              <p class="text-sm text-destructive mb-2">{{ store.topUsersError }}</p>
              <Button variant="outline" size="sm" @click="store.fetchTopUsers()"> Retry </Button>
            </div>
          </template>
          <template v-else-if="!activeUsers.length">
            <div class="text-center py-8">
              <p class="text-sm text-muted-foreground">No user activity for this period</p>
            </div>
          </template>
          <template v-else>
            <div class="space-y-3">
              <div
                v-for="(user, idx) in activeUsers"
                :key="user.user_email"
                class="flex items-center gap-3 rounded-lg px-3 py-2.5 -mx-1 transition-colors hover:bg-muted/50"
              >
                <span
                  class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0"
                  :class="
                    idx === 0 ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'
                  "
                >
                  {{ idx + 1 }}
                </span>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center justify-between">
                    <p class="text-sm font-medium text-foreground truncate">
                      {{ user.user_email }}
                    </p>
                    <span class="text-sm font-semibold text-foreground tabular-nums">
                      {{ formatCurrency(user.revenue) }}
                    </span>
                  </div>
                  <div class="flex items-center gap-2 mt-1">
                    <div class="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        class="h-full rounded-full transition-all"
                        :class="idx === 0 ? 'bg-primary' : 'bg-primary/40'"
                        :style="{
                          width: `${(user.query_count / (activeUsers[0]?.query_count ?? 1)) * 100}%`,
                        }"
                      />
                    </div>
                    <span class="text-xs text-muted-foreground tabular-nums shrink-0">
                      {{ user.query_count.toLocaleString() }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, ref, watch } from 'vue'
import {
  Activity,
  BarChart3,
  CheckCircle,
  DollarSign,
  Download,
  Filter,
  Heart,
  TrendingUp,
  Users,
  UsersRound,
} from 'lucide-vue-next'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  Tooltip as ChartTooltip,
} from 'chart.js'
import { Line, Bar } from 'vue-chartjs'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { endpointsApi } from '@/api/endpoints/endpoints'

import { useAnalyticsStore } from '@/stores/analytics'
import { formatCompactNumber, formatCurrency } from '@/lib/formatters'
import type { TimeRange } from '@/api/types/analytics'
import type { EndpointListItem } from '@/api/types'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  ChartTooltip,
)

const store = useAnalyticsStore()

const icons = {
  checkCircle: markRaw(CheckCircle),
  activity: markRaw(Activity),
  dollarSign: markRaw(DollarSign),
  users: markRaw(Users),
}

const statCardMeta = [
  {
    key: 'active_endpoints' as const,
    label: 'Active Endpoints',
    iconComponent: icons.checkCircle,
    iconBg: 'bg-green-500/10 dark:bg-green-400/10',
    iconFg: 'text-green-600 dark:text-green-400',
    format: formatCompactNumber,
    alwaysPositive: true,
  },
  {
    key: 'total_queries' as const,
    label: 'Total Queries',
    iconComponent: icons.activity,
    iconBg: 'bg-blue-500/10 dark:bg-blue-400/10',
    iconFg: 'text-blue-600 dark:text-blue-400',
    format: formatCompactNumber,
    alwaysPositive: true,
  },
  {
    key: 'total_revenue' as const,
    label: 'Total Revenue',
    iconComponent: icons.dollarSign,
    iconBg: 'bg-emerald-500/10 dark:bg-emerald-400/10',
    iconFg: 'text-emerald-600 dark:text-emerald-400',
    format: formatCurrency,
    alwaysPositive: true,
  },
  {
    key: 'active_users' as const,
    label: 'Active Users',
    iconComponent: icons.users,
    iconBg: 'bg-muted',
    iconFg: 'text-muted-foreground',
    format: formatCompactNumber,
    alwaysPositive: false,
  },
]

const timeRangeOptions: { value: TimeRange; label: string }[] = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: '1y', label: 'Last year' },
]

const endpointsList = ref<EndpointListItem[]>([])

const ALL_SENTINEL = '__all__'

const selectedEndpointId = computed({
  get: () => store.endpointId ?? ALL_SENTINEL,
  set: (v: string) => {
    store.endpointId = v === ALL_SENTINEL ? undefined : v
  },
})

watch(
  () => store.filters,
  () => store.fetchAll(),
  { immediate: true },
)

onMounted(async () => {
  try {
    endpointsList.value = await endpointsApi.list()
  } catch {
    // Silently ignore — dropdown will just show "All Endpoints"
  }
})

const statCards = computed(() => {
  const s = store.summary
  return statCardMeta.map((meta) => {
    const card = s?.[meta.key]
    return {
      label: meta.label,
      formattedValue: card ? meta.format(card.value) : meta.key === 'total_revenue' ? '$0.00' : '0',
      changeLabel: card?.change_label ?? '--',
      changePositive: meta.alwaysPositive && (card?.change_value ?? 0) > 0,
      iconComponent: meta.iconComponent,
      iconBg: meta.iconBg,
      iconFg: meta.iconFg,
    }
  })
})

const sharedScaleOptions = {
  grid: { color: 'rgba(0,0,0,0.04)' },
  ticks: { color: '#9ca3af', font: { size: 11 } },
  border: { display: false },
}

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: sharedScaleOptions,
    y: {
      ...sharedScaleOptions,
      ticks: {
        ...sharedScaleOptions.ticks,
        callback: (v: string | number) => `${Number(v).toLocaleString()}`,
      },
    },
  },
}

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: sharedScaleOptions,
    y: { ...sharedScaleOptions, beginAtZero: true },
  },
}

const revenueChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: sharedScaleOptions,
    y: {
      ...sharedScaleOptions,
      ticks: {
        ...sharedScaleOptions.ticks,
        callback: (v: string | number) => `$${(Number(v) / 1000).toFixed(1)}k`,
      },
    },
  },
}

const queryVolumeChartData = computed(() => ({
  labels: store.timeSeries?.query_volume.map((p) => p.label) ?? [],
  datasets: [
    {
      data: store.timeSeries?.query_volume.map((p) => p.value) ?? [],
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.08)',
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: '#10b981',
      tension: 0.3,
      fill: true,
    },
  ],
}))

const userActivityChartData = computed(() => ({
  labels: store.timeSeries?.user_activity.map((p) => p.label) ?? [],
  datasets: [
    {
      data: store.timeSeries?.user_activity.map((p) => p.value) ?? [],
      backgroundColor: '#2dd4bf',
      borderRadius: 6,
      barPercentage: 0.55,
    },
  ],
}))

const revenueChartData = computed(() => ({
  labels: store.timeSeries?.revenue.map((p) => p.label) ?? [],
  datasets: [
    {
      data: store.timeSeries?.revenue.map((p) => p.value) ?? [],
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.12)',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.4,
      fill: true,
    },
  ],
}))

const isQueryVolumeEmpty = computed(() => !store.timeSeries?.query_volume.some((p) => p.value > 0))
const isUserActivityEmpty = computed(
  () => !store.timeSeries?.user_activity.some((p) => p.value > 0),
)
const isRevenueEmpty = computed(() => !store.timeSeries?.revenue.some((p) => p.value > 0))

const activeUsers = computed(() => store.topUsers?.users ?? [])
</script>
