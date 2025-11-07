<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      class="max-w-6xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl"
    >
      <div class="flex-shrink-0 border-b bg-green-50">
        <DialogHeader class="p-6">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-3 rounded-lg bg-green-100">
              <Calculator class="h-6 w-6 text-green-600" />
            </div>
            <div>
              <DialogTitle class="heading-2 text-gray-900">Revenue Details</DialogTitle>
              <DialogDescription class="body-base text-green-700">Complete revenue breakdown and analytics</DialogDescription>
            </div>
          </div>
        </DialogHeader>
      </div>

      <div class="flex-1 min-h-0 overflow-y-auto p-6">
        <div class="space-y-6">
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div class="text-center p-4 bg-green-50 rounded-lg">
              <p class="text-3xl font-bold text-green-600 mb-1">
                ${{ getRevenueDetails().total }}
              </p>
              <p class="body-sm text-green-700">Total Revenue</p>
            </div>
            <div class="text-center p-4 bg-gray-50 rounded-lg">
              <p class="text-2xl font-bold text-gray-900 mb-1">
                ${{ getRevenueDetails().thisMonth }}
              </p>
              <p class="body-sm text-gray-600">This Month</p>
            </div>
            <div class="text-center p-4 bg-gray-50 rounded-lg">
              <p class="text-2xl font-bold text-gray-900 mb-1">
                ${{ getRevenueDetails().lastMonth }}
              </p>
              <p class="body-sm text-gray-600">Last Month</p>
            </div>
            <div class="text-center p-4 bg-gray-50 rounded-lg">
              <p class="text-2xl font-bold text-green-600 mb-1">
                {{ getRevenueDetails().growth }}
              </p>
              <p class="body-sm text-gray-600">Growth</p>
            </div>
          </div>

          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h3 class="heading-3 text-gray-900 mb-4">Top Performing Endpoints</h3>
            <div class="space-y-4">
              <div
                v-for="endpoint in getRevenueDetails().topEndpoints"
                :key="endpoint.name"
                class="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div>
                  <h4 class="font-medium text-gray-900">{{ endpoint.name }}</h4>
                  <p class="body-sm text-gray-600">
                    {{ endpoint.percentage }}% of total revenue
                  </p>
                </div>
                <div class="text-right">
                  <p class="font-semibold text-green-600">${{ endpoint.revenue }}</p>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h3 class="heading-3 text-gray-900 mb-4">Monthly Revenue Trend</h3>
            <div class="grid grid-cols-5 gap-4">
              <div
                v-for="month in getRevenueDetails().monthlyBreakdown"
                :key="month.month"
                class="text-center p-3 bg-gray-50 rounded-lg"
              >
                <p class="body-sm text-gray-600 mb-1">{{ month.month }}</p>
                <p class="font-semibold text-gray-900">${{ month.revenue }}</p>
              </div>
            </div>
          </div>

          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h3 class="heading-3 text-gray-900 mb-4">Key Metrics</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="text-center p-3 bg-blue-50 rounded-lg">
                <p class="text-xl font-bold text-blue-600 mb-1">
                  {{ getRevenueDetails().metrics.totalTransactions }}
                </p>
                <p class="text-xs text-blue-700">Total Transactions</p>
              </div>
              <div class="text-center p-3 bg-purple-50 rounded-lg">
                <p class="text-xl font-bold text-purple-600 mb-1">
                  {{ getRevenueDetails().metrics.avgRevenuePerTransaction }}
                </p>
                <p class="text-xs text-purple-700">Avg per Transaction</p>
              </div>
              <div class="text-center p-3 bg-orange-50 rounded-lg">
                <p class="text-xl font-bold text-orange-600 mb-1">
                  {{ getRevenueDetails().metrics.paidUsers }}
                </p>
                <p class="text-xs text-orange-700">Paid Users</p>
              </div>
              <div class="text-center p-3 bg-green-50 rounded-lg">
                <p class="text-xl font-bold text-green-600 mb-1">
                  {{ getRevenueDetails().metrics.conversionRate }}
                </p>
                <p class="text-xs text-green-700">Conversion Rate</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Calculator } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getRevenueDetails } from '@/composables/useRevenue'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})
</script>