<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <BarChart3 class="h-6 w-6 text-[var(--color-accent)]" />
        <h1 class="text-2xl font-bold text-gray-900">Analytics</h1>
      </div>
      <p class="text-gray-600">Aggregated analytics across your endpoints</p>
    </div>

    <!-- Aggregated Stats (moved from Endpoints) -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div class="bg-white rounded-lg p-6 border border-gray-200">
        <div class="flex items-center justify-between mb-2">
          <p class="text-sm font-medium text-gray-500">Active</p>
          <CheckCircle class="w-4 h-4 text-green-500" />
        </div>
        <p class="text-2xl font-semibold text-gray-900">{{ activeCount }}</p>
        <p class="text-xs text-green-600 mt-2">+2 from last week</p>
      </div>

      <div class="bg-white rounded-lg p-6 border border-gray-200">
        <div class="flex items-center justify-between mb-2">
          <p class="text-sm font-medium text-gray-500">Total Queries</p>
          <Activity class="w-4 h-4 text-blue-500" />
        </div>
        <p class="text-2xl font-semibold text-gray-900">{{ analytics.totalRequests }}</p>
        <p class="text-xs text-blue-600 mt-2">↑ 12% from yesterday</p>
      </div>

      <div class="bg-white rounded-lg p-6 border border-gray-200">
        <div class="flex items-center justify-between mb-2">
          <p class="text-sm font-medium text-gray-500">Revenue</p>
          <DollarSign class="w-4 h-4 text-green-500" />
        </div>
        <p class="text-2xl font-semibold text-gray-900">{{ analytics.totalEarnings }}</p>
        <p class="text-xs text-green-600 mt-2">↑ {{ analytics.monthlyEarnings }} this month</p>
      </div>

      <div class="bg-white rounded-lg p-6 border border-gray-200">
        <div class="flex items-center justify-between mb-2">
          <p class="text-sm font-medium text-gray-500">Success Rate</p>
          <TrendingUp class="w-4 h-4 text-green-500" />
        </div>
        <p class="text-2xl font-semibold text-gray-900">{{ analytics.successRate }}</p>
        <p class="text-xs text-gray-500 mt-2">Last 24 hours</p>
      </div>
    </div>

    <!-- Placeholder for future charts -->
    <div class="bg-white rounded-lg p-8 border border-gray-200 text-center text-gray-500">
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

const activeCount = computed(() => endpointsStore.endpoints.filter(e => e.status === 'published').length)
const analytics = getMockAnalytics('endpoint')
</script>




