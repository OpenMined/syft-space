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
        <Button variant="outline" @click="exportAllData" class="gap-2">
          <Download class="h-4 w-4" />
          Export All Data
        </Button>
      </div>
    </div>

    <!-- Filters (compact inline) -->
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
              <Select v-model="selectedTimeRange">
                <SelectTrigger class="w-[150px] h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="opt in timeRangeOptions" :key="opt" :value="opt">
                    {{ opt }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-sm text-muted-foreground">Endpoint:</span>
              <Select v-model="selectedEndpoint">
                <SelectTrigger class="w-[170px] h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="opt in endpointOptions" :key="opt" :value="opt">
                    {{ opt }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-sm text-muted-foreground">Dataset:</span>
              <Select v-model="selectedDataset">
                <SelectTrigger class="w-[150px] h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="opt in datasetOptions" :key="opt" :value="opt">
                    {{ opt }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Stats Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <Card
        v-for="stat in mockStatCards"
        :key="stat.label"
        class="transition-shadow hover:shadow-md"
      >
        <CardContent class="p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-medium text-muted-foreground">{{ stat.label }}</p>
            <div
              class="w-8 h-8 rounded-lg flex items-center justify-center"
              :class="iconBg(stat.icon)"
            >
              <CheckCircle v-if="stat.icon === 'check'" class="w-4 h-4" :class="iconFg(stat.icon)" />
              <Activity v-else-if="stat.icon === 'activity'" class="w-4 h-4" :class="iconFg(stat.icon)" />
              <DollarSign v-else-if="stat.icon === 'dollar'" class="w-4 h-4" :class="iconFg(stat.icon)" />
              <Users v-else class="w-4 h-4" :class="iconFg(stat.icon)" />
            </div>
          </div>
          <p class="text-3xl font-bold text-foreground tracking-tight">{{ stat.value }}</p>
          <p
            class="text-xs mt-1.5"
            :class="
              stat.changeType === 'positive'
                ? 'text-green-600 dark:text-green-400'
                : 'text-muted-foreground'
            "
          >
            {{ stat.change }}
          </p>
        </CardContent>
      </Card>
    </div>

    <!-- Charts Row 1 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <TrendingUp class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">Query Volume Trends</span>
          </div>
          <p class="text-xs text-muted-foreground mb-5">Query count over time (30d)</p>
          <div class="h-52">
            <Line :data="queryVolumeChartData" :options="lineChartOptions" />
          </div>
        </CardContent>
      </Card>

      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <UsersRound class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">User Activity</span>
          </div>
          <p class="text-xs text-muted-foreground mb-5">Daily active users this week</p>
          <div class="h-52">
            <Bar :data="userActivityChartData" :options="barChartOptions" />
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Charts Row 2 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <Card class="transition-shadow hover:shadow-md">
        <CardContent class="p-5">
          <div class="flex items-center gap-2 mb-0.5">
            <DollarSign class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">Revenue Overview</span>
          </div>
          <p class="text-xs text-muted-foreground mb-5">Quarterly revenue breakdown</p>
          <div class="h-52">
            <Line :data="revenueChartData" :options="revenueChartOptions" />
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
          <div class="space-y-3">
            <div
              v-for="(user, idx) in mockActiveUsers"
              :key="user.name"
              class="flex items-center gap-3 rounded-lg px-3 py-2.5 -mx-1 transition-colors hover:bg-muted/50"
            >
              <span
                class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0"
                :class="idx === 0 ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'"
              >
                {{ idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <p class="text-sm font-medium text-foreground">{{ user.name }}</p>
                  <span class="text-sm font-semibold text-foreground tabular-nums">
                    ${{ user.revenue.toLocaleString('en-US', { minimumFractionDigits: 2 }) }}
                  </span>
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <div class="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="idx === 0 ? 'bg-primary' : 'bg-primary/40'"
                      :style="{ width: `${(user.queries / (mockActiveUsers[0]?.queries ?? 1)) * 100}%` }"
                    ></div>
                  </div>
                  <span class="text-xs text-muted-foreground tabular-nums shrink-0">
                    {{ user.queries.toLocaleString() }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Most Queried Topics (full width) -->
    <Card class="transition-shadow hover:shadow-md">
      <CardContent class="p-5">
        <div class="flex items-center justify-between mb-0.5">
          <div class="flex items-center gap-2">
            <Search class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold text-foreground">Most Queried Topics</span>
          </div>
          <Badge variant="outline" class="text-[11px] font-normal tracking-wide uppercase">
            Anonymized
          </Badge>
        </div>
        <p class="text-xs text-muted-foreground mb-5">
          Top query topics across all endpoints (30d)
        </p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2.5">
          <div
            v-for="topic in mockTrendingTopics"
            :key="topic.rank"
            class="flex items-center gap-3 rounded-lg px-3 py-2 -mx-1 transition-colors hover:bg-muted/50"
          >
            <span
              class="w-6 h-6 rounded-full text-[11px] font-bold flex items-center justify-center shrink-0"
              :class="topic.rank <= 3 ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'"
            >
              {{ topic.rank }}
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm text-foreground truncate pr-2">{{ topic.topic }}</span>
                <div class="flex items-center gap-1.5 shrink-0">
                  <span class="text-xs text-muted-foreground tabular-nums">
                    {{ topic.volume.toLocaleString() }}
                  </span>
                  <TrendingUp
                    v-if="topic.trend === 'up'"
                    class="h-3 w-3 text-green-500"
                  />
                  <TrendingDown
                    v-else-if="topic.trend === 'down'"
                    class="h-3 w-3 text-red-400"
                  />
                  <Minus v-else class="h-3 w-3 text-muted-foreground" />
                  <span
                    class="text-[11px] tabular-nums"
                    :class="{
                      'text-green-600 dark:text-green-400': topic.trend === 'up',
                      'text-red-500': topic.trend === 'down',
                      'text-muted-foreground': topic.trend === 'stable',
                    }"
                  >
                    {{ topic.trend === 'down' ? '-' : '+' }}{{ topic.changePercent }}%
                  </span>
                </div>
              </div>
              <div class="h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="topic.rank <= 3 ? 'bg-primary/70' : 'bg-primary/35'"
                  :style="{ width: `${(topic.volume / (mockTrendingTopics[0]?.volume ?? 1)) * 100}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  BarChart3,
  CheckCircle,
  Activity,
  DollarSign,
  Users,
  TrendingUp,
  TrendingDown,
  Minus,
  UsersRound,
  Heart,
  Filter,
  Download,
  Search,
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
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  mockStatCards,
  mockActiveUsers,
  mockQueryVolumeLabels,
  mockQueryVolumeData,
  mockUserActivityLabels,
  mockUserActivityData,
  mockRevenueLabels,
  mockRevenueData,
  mockTrendingTopics,
  timeRangeOptions,
  endpointOptions,
  datasetOptions,
} from '@/stores/analyticsData'
import { toast } from 'vue-sonner'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  ChartTooltip,
)

const selectedTimeRange = ref('Last 30 days')
const selectedEndpoint = ref('All Endpoints')
const selectedDataset = ref('All Datasets')

function iconBg(icon: string) {
  const map: Record<string, string> = {
    check: 'bg-green-500/10 dark:bg-green-400/10',
    activity: 'bg-blue-500/10 dark:bg-blue-400/10',
    dollar: 'bg-emerald-500/10 dark:bg-emerald-400/10',
    users: 'bg-muted',
  }
  return map[icon] ?? 'bg-muted'
}

function iconFg(icon: string) {
  const map: Record<string, string> = {
    check: 'text-green-600 dark:text-green-400',
    activity: 'text-blue-600 dark:text-blue-400',
    dollar: 'text-emerald-600 dark:text-emerald-400',
    users: 'text-muted-foreground',
  }
  return map[icon] ?? 'text-muted-foreground'
}

const sharedScaleOptions = {
  grid: { color: 'rgba(0,0,0,0.04)' },
  ticks: { color: '#9ca3af', font: { size: 11 } },
  border: { display: false },
}

const queryVolumeChartData = computed(() => ({
  labels: mockQueryVolumeLabels,
  datasets: [
    {
      data: mockQueryVolumeData,
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

const userActivityChartData = computed(() => ({
  labels: mockUserActivityLabels,
  datasets: [
    {
      data: mockUserActivityData,
      backgroundColor: '#2dd4bf',
      borderRadius: 6,
      barPercentage: 0.55,
    },
  ],
}))

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: sharedScaleOptions,
    y: { ...sharedScaleOptions, beginAtZero: true },
  },
}

const revenueChartData = computed(() => ({
  labels: mockRevenueLabels,
  datasets: [
    {
      data: mockRevenueData,
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.12)',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.4,
      fill: true,
    },
  ],
}))

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

function exportAllData() {
  const data = {
    exportedAt: new Date().toISOString(),
    filters: {
      timeRange: selectedTimeRange.value,
      endpoint: selectedEndpoint.value,
      dataset: selectedDataset.value,
    },
    stats: mockStatCards,
    queryVolume: { labels: mockQueryVolumeLabels, data: mockQueryVolumeData },
    userActivity: { labels: mockUserActivityLabels, data: mockUserActivityData },
    revenue: { labels: mockRevenueLabels, data: mockRevenueData },
    trendingTopics: mockTrendingTopics,
    activeUsers: mockActiveUsers,
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `analytics-export-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('Analytics data exported')
}
</script>
