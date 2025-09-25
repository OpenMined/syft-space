<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <BarChart3 class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Usage & Analytics</h1>
    </div>
    <p class="text-gray-600 mb-8">Track costs and analyze usage patterns across all services</p>

    <!-- View Toggle -->
    <Tabs v-model="currentView" class="w-full">
      <TabsList
        class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-2 lg:w-[400px] mb-8"
      >
        <TabsTrigger value="table">Table View</TabsTrigger>
        <TabsTrigger value="analytics">Analytics View</TabsTrigger>
      </TabsList>

      <TabsContent value="table" class="space-y-6">
        <!-- Usage Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
      <!-- Total Queries -->
      <Card class="">
        <CardContent class="p-6">
          <div class="flex items-center space-x-4">
            <div class="p-3 bg-blue-100 rounded-lg">
              <BarChart3 class="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p class="text-sm font-medium text-gray-600">Total Queries</p>
              <p class="text-2xl font-bold">{{ usageStats.totalQueries || 0 }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Completed -->
      <Card>
        <CardContent class="p-6">
          <div class="flex items-center space-x-4">
            <div class="p-3 bg-green-100 rounded-lg">
              <CheckCircle class="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p class="text-sm font-medium text-gray-600">Completed</p>
              <p class="text-2xl font-bold">{{ usageStats.completed || 0 }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Pending -->
      <Card>
        <CardContent class="p-6">
          <div class="flex items-center space-x-4">
            <div class="p-3 bg-yellow-100 rounded-lg">
              <Clock class="h-6 w-6 text-yellow-600" />
            </div>
            <div>
              <p class="text-sm font-medium text-gray-600">Pending</p>
              <p class="text-2xl font-bold">{{ usageStats.pending || 0 }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Total Spent -->
      <Card>
        <CardContent class="p-6">
          <div class="flex items-center space-x-4">
            <div class="p-3 bg-red-100 rounded-lg">
              <TrendingDown class="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p class="text-sm font-medium text-gray-600">Total Spent</p>
              <p class="text-2xl font-bold">${{ usageStats.totalSpent?.toFixed(2) || '0.00' }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Total Earned -->
      <Card>
        <CardContent class="p-6">
          <div class="flex items-center space-x-4">
            <div class="p-3 bg-green-100 rounded-lg">
              <TrendingUp class="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p class="text-sm font-medium text-gray-600">Total Earned</p>
              <p class="text-2xl font-bold">${{ usageStats.totalEarned?.toFixed(2) || '0.00' }}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Query History Section -->
    <Card>
      <CardHeader>
        <div class="flex items-center justify-between">
          <div>
            <CardTitle>Query History</CardTitle>
            <CardDescription>All your queries across all services</CardDescription>
          </div>
          <div class="flex items-center space-x-4">
            <!-- Time Filter -->
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" class="min-w-[120px] justify-between">
                  {{ selectedTimeFilter }}
                  <ChevronDown class="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem @click="selectedTimeFilter = 'All Time'">
                  All Time
                </DropdownMenuItem>
                <DropdownMenuItem @click="selectedTimeFilter = 'Last 7 Days'">
                  Last 7 Days
                </DropdownMenuItem>
                <DropdownMenuItem @click="selectedTimeFilter = 'Last 30 Days'">
                  Last 30 Days
                </DropdownMenuItem>
                <DropdownMenuItem @click="selectedTimeFilter = 'Last 90 Days'">
                  Last 90 Days
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <!-- Status Filter -->
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" class="min-w-[120px] justify-between">
                  {{ selectedStatusFilter }}
                  <ChevronDown class="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem @click="selectedStatusFilter = 'All Status'">
                  All Status
                </DropdownMenuItem>
                <DropdownMenuItem @click="selectedStatusFilter = 'Completed'">
                  Completed
                </DropdownMenuItem>
                <DropdownMenuItem @click="selectedStatusFilter = 'Pending'">
                  Pending
                </DropdownMenuItem>
                <DropdownMenuItem @click="selectedStatusFilter = 'Failed'">
                  Failed
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div class="overflow-x-auto">
          <!-- Table Header -->
          <div class="grid grid-cols-5 gap-4 p-4 border-b text-sm font-medium text-gray-600 uppercase tracking-wider">
            <div>Transaction ID</div>
            <div>Sender</div>
            <div>Recipient</div>
            <div>Amount</div>
            <div>Service</div>
          </div>
          
          <!-- Table Rows -->
          <div v-if="loading" class="p-8 text-center text-gray-500">
            Loading transactions...
          </div>
          <div v-else-if="filteredTransactions.length === 0" class="p-8 text-center text-gray-500">
            No transactions found
          </div>
          <div v-else>
            <div 
              v-for="transaction in filteredTransactions" 
              :key="transaction.id" 
              class="grid grid-cols-5 gap-4 p-4 border-b hover:bg-gray-50 transition-colors"
            >
              <TooltipProvider>
                <div class="flex items-center space-x-3">
                  <div class="p-2 bg-blue-100 rounded-lg">
                    <BarChart3 class="h-4 w-4 text-blue-600" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <p class="font-medium text-gray-900 truncate cursor-help">{{ transaction.shortId }}</p>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>{{ transaction.id }}</p>
                      </TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <p class="text-sm text-gray-500 truncate cursor-help">{{ transaction.id }}</p>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>{{ transaction.id }}</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div class="text-gray-900 truncate cursor-help">{{ transaction.sender }}</div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{{ transaction.sender }}</p>
                  </TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div class="text-gray-900 truncate cursor-help">{{ transaction.recipient }}</div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{{ transaction.recipient }}</p>
                  </TooltipContent>
                </Tooltip>
                <div class="text-gray-900 font-medium">${{ transaction.amount.toFixed(2) }}</div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div class="text-gray-600 truncate cursor-help">{{ transaction.service }}</div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{{ transaction.service }}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
      </TabsContent>

      <TabsContent value="analytics" class="space-y-6">
        <Card>
          <CardContent class="flex items-center justify-center h-64">
            <div class="text-center">
              <BarChart3 class="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 class="text-lg font-medium text-gray-900 mb-2">Analytics Coming Soon</h3>
              <p class="text-gray-600">Advanced analytics and visualization features will be available here.</p>
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { BarChart3, CheckCircle, Clock, TrendingDown, TrendingUp, ChevronDown } from 'lucide-vue-next'
import type { Transaction } from '@/types'

// Reactive state
const currentView = ref('table')
const selectedTimeFilter = ref('All Time')
const selectedStatusFilter = ref('All Status')
const loading = ref(true)
const transactions = ref<Transaction[]>([])
const usageStats = ref({
  totalQueries: 0,
  completed: 0,
  pending: 0,
  totalSpent: 0,
  totalEarned: 0
})

// Extended transaction interface for display
interface ExtendedTransaction extends Transaction {
  shortId: string
  sender: string
  recipient: string
  app: string
  endpoint: string
}

const extendedTransactions = ref<ExtendedTransaction[]>([])

// Computed filtered transactions
const filteredTransactions = computed(() => {
  return extendedTransactions.value.filter(transaction => {
    const matchesStatus = selectedStatusFilter.value === 'All Status' || 
                         transaction.service === selectedStatusFilter.value.toLowerCase()
    // Add time filtering logic here if needed
    return matchesStatus
  })
})

// Load data on mount
onMounted(async () => {
  try {
    // TODO: Replace with actual API call
    // const stats = await apiService.getUsageStats()
    const stats = {
      apiCalls: 525,
      monthlyUsage: 83.20,
      currentBalance: 43.60
    }
    
    usageStats.value = {
      totalQueries: stats.apiCalls || 0,
      completed: 411,
      pending: 10,
      totalSpent: stats.monthlyUsage || 0,
      totalEarned: 7.10
    }

    // TODO: Replace with actual API call
    // const transactionData = await apiService.getTransactions()
    const transactionData = [
      {
        id: 'cmfz7hchz00feqn3z1f64c6jc',
        description: 'Chat query',
        date: new Date().toISOString(),
        amount: 0.30,
        service: 'research@safari-lab.org/animalsofsouthafrica'
      },
      {
        id: 'cmfz7cqf',
        description: 'Chat query', 
        date: new Date().toISOString(),
        amount: 0.25,
        service: 'data@lexfirm.eu/lexcivillaw'
      }
    ]
    
    transactions.value = transactionData
    
    // Transform transactions for display
    extendedTransactions.value = transactionData.map((transaction, index) => ({
      ...transaction,
      shortId: transaction.id.length > 10 ? transaction.id.substring(0, 10) + '...' : transaction.id,
      sender: 'irina@openmined.org',
      recipient: 'aggregator@openmined.org',
      app: transaction.service || 'claude-sonnet-3.5',
      endpoint: '/chat'
    }))
  } catch (error) {
    console.error('Error loading usage data:', error)
  } finally {
    loading.value = false
  }
})
</script>