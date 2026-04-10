<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <BarChart3 class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Analytics</h1>
      </div>
      <p class="body-lg text-muted-foreground">Aggregated analytics across your APIs</p>
    </div>

    <!-- Aggregated Stats (moved from Endpoints) -->
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
          <p class="body-sm font-medium text-muted-foreground">Total Queries</p>
          <Activity class="w-4 h-4 text-blue-500 dark:text-blue-400" />
        </div>
        <p class="text-3xl font-bold text-foreground">{{ analytics.totalRequests }}</p>
        <p class="body-sm text-blue-600 dark:text-blue-400 mt-2">↑ 12% from yesterday</p>
      </div>

      <div class="bg-card rounded-lg p-6 border border-border">
        <div class="flex items-center justify-between mb-2">
          <p class="body-sm font-medium text-muted-foreground">Revenue</p>
          <DollarSign class="w-4 h-4 text-green-500 dark:text-green-400" />
        </div>
        <p class="text-3xl font-bold text-foreground">{{ analytics.totalEarnings }}</p>
        <p class="body-sm text-green-600 dark:text-green-400 mt-2">
          ↑ {{ analytics.monthlyEarnings }} this month
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

    <!-- Placeholder for future charts -->
    <div class="bg-card rounded-lg p-8 border border-border text-center text-muted-foreground">
      More detailed charts and breakdowns coming soon.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircle, Activity, DollarSign, TrendingUp, BarChart3 } from 'lucide-vue-next'
import { useEndpointsStore } from '@/stores/endpoints'
import { getMockAnalytics } from '@/stores/mockData'

const endpointsStore = useEndpointsStore()

const activeCount = computed(() => endpointsStore.endpoints.filter((e) => e.published).length)
const analytics = getMockAnalytics('endpoint')
</script>
