<template>
  <ErrorBoundary
    :can-retry="true"
    :show-details="true"
    custom-title="Dashboard Loading Error"
    custom-message="There was a problem loading the dashboard. Please try again."
    @retry="refreshDashboard"
  >
    <div class="min-h-screen bg-gradient-to-br from-white via-blue-50/20 to-purple-50/30">
      <div class="max-w-6xl mx-auto px-6 lg:px-8 py-8 lg:py-12">
        <!-- Hero Section -->
        <div class="text-center mb-16">
          <h1 class="heading-1 font-light text-gray-900 mb-4">
            Welcome to your <span class="font-medium text-blue-600">Syft AI Space</span>
          </h1>
          <p class="body-lg text-gray-600 max-w-2xl mx-auto">A Space where you can turn data and models into shareable workflows — exposing them through secure endpoints under your own rules for privacy, payments, and human oversight.</p>
        </div>
          
        <!-- Action Cards -->
        <div class="mb-12">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    @click="showCreateEndpointModal = true"
                    class="group bg-white hover:bg-blue-50 rounded-xl p-6 text-left transition-all duration-200 border border-gray-200 hover:border-blue-300 hover:shadow-lg hover:-translate-y-1"
            >
                    <div class="flex flex-col items-start space-y-3">
                      <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center group-hover:bg-blue-200 transition-colors">
                        <FolderOpen class="w-6 h-6 text-blue-600" />
                      </div>
                      <div>
                        <div class="font-medium text-gray-900">
                          Publish your first data source
                        </div>
                        <div class="text-sm text-gray-500 mt-1">
                          Add files or link a source
                        </div>
                      </div>
                    </div>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Add files or link a data source, then publish</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    @click="$router.push('/datasets')"
                    class="group bg-white hover:bg-green-50 rounded-xl p-6 text-left transition-all duration-200 border border-gray-200 hover:border-green-300 hover:shadow-lg hover:-translate-y-1"
            >
                    <div class="flex flex-col items-start space-y-3">
                      <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center group-hover:bg-green-200 transition-colors">
                        <Settings class="w-6 h-6 text-green-600" />
                      </div>
                      <div>
                        <div class="font-medium text-gray-900">
                          Manage your data
                        </div>
                        <div class="text-sm text-gray-500 mt-1">
                          Datasets and sources
                        </div>
                      </div>
                    </div>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>View and organize datasets</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    @click="$router.push('/models')"
                    class="group bg-white hover:bg-purple-50 rounded-xl p-6 text-left transition-all duration-200 border border-gray-200 hover:border-purple-300 hover:shadow-lg hover:-translate-y-1"
            >
                    <div class="flex flex-col items-start space-y-3">
                      <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center group-hover:bg-purple-200 transition-colors">
                        <Brain class="w-6 h-6 text-purple-600" />
                      </div>
                      <div>
                        <div class="font-medium text-gray-900">
                          Manage your models
                        </div>
                        <div class="text-sm text-gray-500 mt-1">
                          vLLM, Ollama, or custom
                        </div>
                      </div>
                    </div>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Manage AI model endpoints</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    @click="$router.push('/inbox')"
                    class="group bg-white hover:bg-orange-50 rounded-xl p-6 text-left transition-all duration-200 border border-gray-200 hover:border-orange-300 hover:shadow-lg hover:-translate-y-1 relative"
            >
                    <div class="flex flex-col items-start space-y-3">
                      <div class="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center group-hover:bg-orange-200 transition-colors">
                        <ShieldCheck class="w-6 h-6 text-orange-600" />
                      </div>
                      <div>
                        <div class="font-medium text-gray-900">
                          Review usage & requests
                        </div>
                        <div class="text-sm text-gray-500 mt-1">
                          {{ inboxStore.unreadCount }} pending
                        </div>
                      </div>
                    </div>
                    <div v-if="inboxStore.unreadCount > 0" class="absolute -top-2 -right-2 w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Review usage and access requests</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        <!-- Compact Overview -->
        <div class="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-100 p-4 mb-10 shadow-sm">
          <div class="flex items-center justify-center gap-8">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="$router.push('/datasets')" class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-blue-50 transition-colors">
                    <Database class="w-4 h-4 text-blue-600" />
                    <span class="text-2xl font-light text-gray-900">12</span>
                    <span class="text-sm text-gray-500">Datasets</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>View all datasets</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            <div class="w-px h-8 bg-gray-200"></div>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="$router.push('/models')" class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-purple-50 transition-colors">
                    <Brain class="w-4 h-4 text-purple-600" />
                    <span class="text-2xl font-light text-gray-900">7</span>
                    <span class="text-sm text-gray-500">Models</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Manage AI models</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            <div class="w-px h-8 bg-gray-200"></div>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="$router.push('/inbox')" class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-orange-50 transition-colors">
                    <ShieldCheck class="w-4 h-4 text-orange-600" />
                    <span class="text-2xl font-light text-gray-900">{{ inboxStore.unreadCount }}</span>
                    <span class="text-sm text-gray-500">Requests</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Review pending requests</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            <div class="w-px h-8 bg-gray-200"></div>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="revenueDialogOpen = true" class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-green-50 transition-colors">
                    <TrendingUp class="w-4 h-4 text-green-600" />
                    <span class="text-2xl font-light text-gray-900">${{ getTotalRevenue().total }}</span>
                    <span class="text-sm text-gray-500">Revenue</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>View detailed revenue analytics</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        <!-- Recent Activity -->
        <div class="bg-white rounded-xl border border-gray-100 p-6 mb-10 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <h2 class="heading-3 text-gray-900">Recent Activity</h2>
            <button
              @click="$router.push('/inbox')"
              class="text-sm text-blue-600 hover:text-blue-700"
            >
              View all →
            </button>
          </div>

          <div v-if="inboxStore.unreadCount === 0" class="text-center py-8">
            <p class="body-sm text-gray-400">No pending requests</p>
          </div>

          <div v-else class="space-y-3 max-h-64 overflow-y-auto">
            <div
              v-for="item in inboxStore.activeItems.slice(0, 3)"
              :key="item.id"
              class="flex items-start gap-3 p-4 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
              @click="openItemDialog(item)"
            >
              <div :class="`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${getSourceColor(item.source)}`">
                <component :is="getSourceIcon(item.source)" class="w-4 h-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-2">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="body-sm font-medium text-primary truncate">{{ item.source }}</span>
                      <div v-if="!item.read" class="w-2 h-2 bg-blue-500 rounded-full"></div>
                    </div>
                    <p class="body-sm text-primary truncate mb-1">{{ item.title }}</p>
                    <p class="text-xs font-light text-light">{{ formatTimestamp(item.timestamp) }}</p>
                  </div>
                  <div v-if="item.actions" class="flex items-center gap-1" @click.stop>
                    <Button
                      v-if="item.actions.positive"
                      size="sm"
                      class="h-6 px-2 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-strong)] text-white"
                      @click="handlePositiveAction(item)"
                    >
                      {{ item.actions.positive.label }}
                    </Button>
                    <Button
                      v-if="item.actions.negative"
                      size="sm"
                      variant="outline"
                      class="h-6 px-2 text-xs border-gray-300 hover:border-gray-400"
                      @click="handleNegativeAction(item)"
                    >
                      {{ item.actions.negative.label }}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Getting Started -->
        <div class="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-6 border border-blue-100">
          <h3 class="heading-3 text-gray-900 mb-4 flex items-center gap-2">
            <Zap class="w-4 h-4 text-blue-600" />
            Quick Start Guide
          </h3>
          
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <button class="group flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
              <FileText class="w-4 h-4 text-blue-600" />
              <div class="text-left">
                <div class="body-sm font-medium text-gray-900">Publish Documents</div>
                <div class="text-xs text-gray-500">Share PDFs securely</div>
              </div>
            </button>
            
            <button class="group flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
              <Zap class="w-4 h-4 text-indigo-600" />
              <div class="text-left">
                <div class="body-sm font-medium text-gray-900">Connect AI Models</div>
                <div class="text-xs text-gray-500">Link AI endpoints</div>
              </div>
            </button>
            
            <button class="group flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
              <Shield class="w-4 h-4 text-purple-600" />
              <div class="text-left">
                <div class="body-sm font-medium text-gray-900">Configure Access</div>
                <div class="text-xs text-gray-500">Set permissions</div>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- Item Detail Dialog -->
      <Dialog v-model:open="dialogOpen">
        <DialogContent
          v-if="selectedItem"
          class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl"
        >
          <div class="flex-shrink-0 border-b bg-gray-50">
            <DialogHeader class="p-6 pb-4">
              <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3">
                  <div :class="`p-3 rounded-lg ${getSourceColor(selectedItem.source)}`">
                    <component :is="getSourceIcon(selectedItem.source)" class="h-5 w-5" />
                  </div>
                  <div>
                    <div class="flex items-center gap-2 mb-1">
                      <Badge variant="outline" class="text-xs">{{ selectedItem.source }}</Badge>
                      <div
                        v-if="!selectedItem.read"
                        class="flex items-center gap-1 text-xs text-purple-600"
                      >
                        <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
                        <span>New</span>
                      </div>
                    </div>
                    <span class="text-sm text-gray-500">
                      {{ formatTimestamp(selectedItem.timestamp) }}
                    </span>
                  </div>
                </div>
              </div>
              <DialogTitle class="text-2xl font-semibold">{{ selectedItem.title }}</DialogTitle>
              <DialogDescription class="mt-2 body-base">{{
                selectedItem.summary
              }}</DialogDescription>
            </DialogHeader>
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto">
            <div class="p-6">
              <div
                class="prose prose-sm max-w-none prose-headings:font-semibold prose-h2:text-lg prose-h3:text-base prose-p:text-gray-600 prose-strong:text-gray-900 prose-code:text-purple-600 prose-pre:bg-gray-50 prose-pre:border prose-li:text-gray-600"
                v-html="markdownToHtml(selectedItem.longDescription)"
              />
            </div>
          </div>

          <div class="flex-shrink-0 border-t bg-gray-50">
            <DialogFooter class="p-6 pt-4">
              <div class="flex items-center justify-between w-full">
                <div class="flex items-center gap-4">
                  <Button
                    variant="ghost"
                    size="default"
                    class="text-gray-600 hover:text-gray-900"
                    @click="
                      () => {
                        selectedItem && dismissItem(selectedItem)
                        dialogOpen = false
                      }
                    "
                  >
                    <Trash2 class="h-4 w-4 mr-2" />
                    Dismiss
                  </Button>
                </div>
                <div class="flex items-center gap-3">
                  <Button
                    v-if="selectedItem.actions?.negative"
                    variant="outline"
                    size="default"
                    @click="selectedItem && handleNegativeAction(selectedItem)"
                  >
                    {{ selectedItem.actions.negative.label }}
                  </Button>
                  <Button
                    v-if="selectedItem.actions?.positive"
                    variant="default"
                    size="default"
                    class="bg-purple-600 hover:bg-purple-700"
                    @click="selectedItem && handlePositiveAction(selectedItem)"
                  >
                    {{ selectedItem.actions.positive.label }}
                  </Button>
                </div>
              </div>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      <!-- Revenue Details Dialog -->
      <Dialog v-model:open="revenueDialogOpen">
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
    </div>
  </ErrorBoundary>

  <!-- Create Endpoint Modal -->
  <CreateEndpointModal v-model:open="showCreateEndpointModal" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  Database,
  Brain,
  Users,
  Gauge,
  Calculator,
  Activity,
  AlertCircle,
  Info,
  Trash2,
  FolderOpen,
  Settings,
  ShieldCheck,
  TrendingUp,
  FileText,
  Zap,
  Shield,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useInboxStore, type InboxItem } from '@/stores/inbox'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import CreateEndpointModal from '@/components/CreateEndpointModal.vue'

const inboxStore = useInboxStore()

const selectedItem = ref<InboxItem | null>(null)
const dialogOpen = ref(false)
const revenueDialogOpen = ref(false)
const showCreateEndpointModal = ref(false)

const openItemDialog = (item: InboxItem) => {
  selectedItem.value = item
  dialogOpen.value = true
  if (!item.read) {
    inboxStore.markAsRead(item.id)
  }
}

const dismissItem = (item: InboxItem) => {
  inboxStore.dismissItem(item.id)
  if (selectedItem.value?.id === item.id) {
    dialogOpen.value = false
  }
}

const handlePositiveAction = (item: InboxItem) => {
  if (item.actions?.positive?.handler) {
    item.actions.positive.handler()
  }
  dismissItem(item)
}

const handleNegativeAction = (item: InboxItem) => {
  if (item.actions?.negative?.handler) {
    item.actions.negative.handler()
  }
  dismissItem(item)
}

const getSourceIcon = (source: string) => {
  if (source === 'Human-in-the-Loop Policy') return Users
  if (source.includes('Rate Limiting')) return Gauge
  if (source === 'Accounting Policy') return Calculator
  if (source === 'OpenTelemetry Observability Policy') return Activity
  if (source.includes('Security')) return AlertCircle
  return Info
}

const getSourceColor = (source: string) => {
  if (source === 'Human-in-the-Loop Policy') return 'text-orange-600 bg-orange-100'
  if (source.includes('Rate Limiting')) return 'text-blue-600 bg-blue-100'
  if (source === 'Accounting Policy') return 'text-green-600 bg-green-100'
  if (source === 'OpenTelemetry Observability Policy') return 'text-purple-600 bg-purple-100'
  if (source.includes('Security')) return 'text-red-600 bg-red-100'
  if (source.includes('Update')) return 'text-blue-600 bg-blue-100'
  if (source.includes('Usage')) return 'text-purple-600 bg-purple-100'
  return 'text-gray-600 bg-gray-100'
}

const formatTimestamp = (date: Date) => {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`
  if (days < 7) return `${days} day${days > 1 ? 's' : ''} ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

const refreshDashboard = () => {
  console.log('Refreshing dashboard data...')
}

const getTotalRevenue = () => {
  return {
    total: '2,847.23',
    growth: '+24.3%',
  }
}

const getRevenueDetails = () => {
  return {
    total: '2,847.23',
    thisMonth: '524.80',
    lastMonth: '423.15',
    growth: '+24.3%',
    topEndpoints: [
      { name: 'Financial Analytics API', revenue: '1,142.50', percentage: 40.1 },
      { name: 'Customer Insights API', revenue: '856.75', percentage: 30.1 },
      { name: 'Marketing Data API', revenue: '523.40', percentage: 18.4 },
      { name: 'Research Dataset API', revenue: '324.58', percentage: 11.4 },
    ],
    monthlyBreakdown: [
      { month: 'Jan', revenue: 384.2 },
      { month: 'Feb', revenue: 421.5 },
      { month: 'Mar', revenue: 456.8 },
      { month: 'Apr', revenue: 423.15 },
      { month: 'May', revenue: 524.8 },
    ],
    metrics: {
      totalTransactions: '47,234',
      avgRevenuePerTransaction: '$0.060',
      paidUsers: '1,847',
      conversionRate: '23.4%',
    },
  }
}

function markdownToHtml(markdown: string): string {
  let html = markdown
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/```(\w+)?\n([^`]+)```/g, '<pre><code>$2</code></pre>')
    .replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" class="text-purple-600 hover:text-purple-700 underline">$1</a>',
    )
    .replace(/\n\n/g, '</p><p>')
    .split('\n')
    .map((line) => {
      if (/^\d+\.\s/.test(line)) {
        return '<li>' + line.substring(line.indexOf('.') + 2) + '</li>'
      } else if (/^-\s/.test(line)) {
        return '<li>' + line.substring(2) + '</li>'
      }
      return line
    })
    .join('\n')

  html = '<p>' + html + '</p>'
  html = html.replace(/<p>\s*<\/p>/g, '')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => {
    if (match.includes('<li>1.')) {
      return '<ol class="list-decimal list-inside space-y-1">' + match + '</ol>'
    }
    return '<ul class="list-disc list-inside space-y-1">' + match + '</ul>'
  })

  return html
}
</script>