<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <Home class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Home</h1>
    </div>
    <p class="text-gray-600 mb-8">Share access to your data and models safely, privately, and on your own terms</p>

    <!-- Dashboard metrics -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <!-- Total Datasets -->
      <div @click="$router.push('/datasets')"
        class="bg-white p-6 rounded-lg shadow border border-gray-200 cursor-pointer hover:shadow-md hover:border-blue-300 transition-all duration-200">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-gray-600">Total Datasets</h3>
          <div class="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
            <Database class="w-5 h-5 text-blue-600" />
          </div>
        </div>
        <div class="text-3xl font-bold text-gray-900 mb-2">12</div>
        <p class="text-sm text-gray-500">3 datasets added this month</p>
      </div>

      <!-- Total Models -->
      <div @click="$router.push('/models')"
        class="bg-white p-6 rounded-lg shadow border border-gray-200 cursor-pointer hover:shadow-md hover:border-purple-300 transition-all duration-200">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-gray-600">Total Models</h3>
          <div class="w-8 h-8 bg-purple-50 rounded-lg flex items-center justify-center">
            <Brain class="w-5 h-5 text-purple-600" />
          </div>
        </div>
        <div class="text-3xl font-bold text-gray-900 mb-2">7</div>
        <p class="text-sm text-gray-500">2 models deployed recently</p>
      </div>

      <!-- Total Endpoints -->
      <div @click="$router.push('/endpoints')"
        class="bg-white p-6 rounded-lg shadow border border-gray-200 cursor-pointer hover:shadow-md hover:border-orange-300 transition-all duration-200">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-gray-600">Total Endpoints</h3>
          <div class="w-8 h-8 bg-orange-50 rounded-lg flex items-center justify-center">
            <Server class="w-5 h-5 text-orange-600" />
          </div>
        </div>
        <div class="text-3xl font-bold text-gray-900 mb-2">4</div>
        <p class="text-sm text-gray-500">1 endpoint active this week</p>
      </div>

      <!-- System Status -->
      <div @click="$router.push('/settings')"
        class="bg-white p-6 rounded-lg shadow border border-gray-200 cursor-pointer hover:shadow-md hover:border-green-300 transition-all duration-200">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-gray-600">System Status</h3>
          <div class="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center">
            <CheckCircle class="w-5 h-5 text-green-600" />
          </div>
        </div>
        <div class="text-3xl font-bold text-green-600 mb-2">All Good</div>
        <p class="text-sm text-gray-500">Your endpoints are running smoothly</p>
      </div>
    </div>

    <!-- Left-Right Split Layout -->
    <div class="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
      <!-- Quick Actions (Left) -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-semibold text-gray-900">Quick Actions</h2>
          <p class="text-sm text-gray-600 mt-1">Common tasks to get you started</p>
        </div>
        <div class="p-6">
          <div class="space-y-4">
            <button @click="$router.push('/create')"
              class="group p-4 rounded-lg border border-gray-200 hover:border-orange-300 hover:shadow-md transition-all duration-200 text-left w-full">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 bg-orange-50 group-hover:bg-orange-100 rounded-lg flex items-center justify-center transition-colors">
                  <Plus class="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <div class="font-medium text-gray-900 group-hover:text-orange-600">Create New Endpoint</div>
                  <div class="text-xs text-gray-500">Share access to your data or AI models</div>
                </div>
              </div>
            </button>

            <button @click="$router.push('/datasets')"
              class="group p-4 rounded-lg border border-gray-200 hover:border-green-300 hover:shadow-md transition-all duration-200 text-left w-full">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 bg-green-50 group-hover:bg-green-100 rounded-lg flex items-center justify-center transition-colors">
                  <Database class="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <div class="font-medium text-gray-900 group-hover:text-green-600">Manage Datasets</div>
                  <div class="text-xs text-gray-500">Add and organize datasets</div>
                </div>
              </div>
            </button>

            <button @click="$router.push('/models')"
              class="group p-4 rounded-lg border border-gray-200 hover:border-purple-300 hover:shadow-md transition-all duration-200 text-left w-full">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 bg-purple-50 group-hover:bg-purple-100 rounded-lg flex items-center justify-center transition-colors">
                  <Brain class="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <div class="font-medium text-gray-900 group-hover:text-purple-600">Manage Models</div>
                  <div class="text-xs text-gray-500">View and configure AI models</div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- Inbox Widget (Right) -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col">
        <div class="px-6 py-4 border-b border-gray-200 flex-shrink-0">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-lg font-semibold text-gray-900">Inbox</h2>
              <p class="text-sm text-gray-600 mt-1">{{ inboxStore.unreadCount }} unread message{{ inboxStore.unreadCount
                !== 1 ? 's' : '' }}</p>
            </div>
            <Button @click="$router.push('/inbox')" variant="outline" size="sm">
              View All
            </Button>
          </div>
        </div>

        <div class="flex-1 min-h-0">
          <div v-if="inboxStore.unreadCount === 0" class="p-8 text-center">
            <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <CheckCircle class="w-6 h-6 text-green-600" />
            </div>
            <h3 class="text-sm font-medium text-gray-900 mb-1">All caught up!</h3>
            <p class="text-xs text-gray-500">No unread messages</p>
          </div>

          <div v-else class="max-h-80 overflow-y-auto">
            <div class="divide-y divide-gray-100">
              <div v-for="item in inboxStore.activeItems.filter(item => !item.read)" :key="item.id"
                class="p-4 hover:bg-gray-50 cursor-pointer" @click="openItemDialog(item)">
                <div class="flex items-start gap-3">
                  <div
                    :class="`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${getSourceColor(item.source)}`">
                    <component :is="getSourceIcon(item.source)" class="w-4 h-4" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between gap-2">
                      <div class="flex-1 min-w-0">
                        <h3 class="text-sm font-medium text-gray-900 truncate">{{ item.title }}</h3>
                        <p class="text-xs text-gray-500 mt-1 line-clamp-2">{{ item.summary }}</p>
                        <div class="flex items-center gap-2 mt-2">
                          <span class="text-xs text-gray-400">{{ formatTimestamp(item.timestamp) }}</span>
                          <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
                        </div>
                      </div>
                      <div v-if="item.actions" class="flex items-center gap-1 ml-2" @click.stop>
                        <Button v-if="item.actions.positive" size="sm" class="h-6 px-2 text-xs whitespace-nowrap"
                          @click="handlePositiveAction(item)">
                          {{ item.actions.positive.label }}
                        </Button>
                        <Button v-if="item.actions.negative" size="sm" variant="outline"
                          class="h-6 px-2 text-xs whitespace-nowrap" @click="handleNegativeAction(item)">
                          {{ item.actions.negative.label }}
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Query History -->
    <div class="mt-8 bg-white rounded-lg shadow-sm border border-gray-200">
      <div class="px-6 py-4 border-b border-gray-200">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-semibold text-gray-900">Query History</h2>
            <p class="text-sm text-gray-600 mt-1">Recent API access logs and usage</p>
          </div>
          <Button @click="$router.push('/transactions')" variant="outline" size="sm">
            View All
          </Button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-gray-50 border-b border-gray-200">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Transaction ID
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Endpoint</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="transaction in recentTransactions" :key="transaction.id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm font-mono text-gray-900">{{ transaction.id }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center gap-2">
                  <div class="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center">
                    <User class="w-3 h-3 text-gray-600" />
                  </div>
                  <span class="text-sm text-gray-900">{{ transaction.user }}</span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm text-gray-900">{{ transaction.endpoint }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <Badge :class="getStatusColor(transaction.status)" variant="outline" class="text-xs">
                  {{ transaction.status }}
                </Badge>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm font-semibold text-gray-900">${{ transaction.amount }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm text-gray-500">{{ formatTimestamp(new Date(transaction.timestamp)) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="recentTransactions.length === 0" class="p-8 text-center">
          <div class="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center mx-auto mb-3">
            <Activity class="w-6 h-6 text-gray-400" />
          </div>
          <h3 class="text-sm font-medium text-gray-900 mb-1">No queries yet</h3>
          <p class="text-xs text-gray-500">API access logs will appear here</p>
        </div>
      </div>
    </div>

    <!-- Item Detail Dialog -->
    <Dialog v-model:open="dialogOpen">
      <DialogContent v-if="selectedItem" class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl">
        <!-- Header with background -->
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
                    <div v-if="!selectedItem.read" class="flex items-center gap-1 text-xs text-purple-600">
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
            <DialogTitle class="text-xl font-semibold">{{ selectedItem.title }}</DialogTitle>
            <DialogDescription class="mt-2 text-base">{{ selectedItem.summary }}</DialogDescription>
          </DialogHeader>
        </div>

        <!-- Content -->
        <div class="flex-1 min-h-0 overflow-y-auto">
          <div class="p-6">
            <div
              class="prose prose-sm max-w-none prose-headings:font-semibold prose-h2:text-lg prose-h3:text-base prose-p:text-gray-600 prose-strong:text-gray-900 prose-code:text-purple-600 prose-pre:bg-gray-50 prose-pre:border prose-li:text-gray-600"
              v-html="markdownToHtml(selectedItem.longDescription)" />
          </div>
        </div>

        <!-- Footer with actions -->
        <div class="flex-shrink-0 border-t bg-gray-50">
          <DialogFooter class="p-6 pt-4">
            <div class="flex items-center justify-between w-full">
              <div class="flex items-center gap-4">
                <Button variant="ghost" size="default" class="text-gray-600 hover:text-gray-900"
                  @click="dismissItem(selectedItem); dialogOpen = false">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Dismiss
                </Button>
              </div>
              <div class="flex items-center gap-3">
                <Button v-if="selectedItem.actions?.negative" variant="outline" size="default"
                  @click="handleNegativeAction(selectedItem)">
                  {{ selectedItem.actions.negative.label }}
                </Button>
                <Button v-if="selectedItem.actions?.positive" variant="default" size="default"
                  class="bg-purple-600 hover:bg-purple-700" @click="handlePositiveAction(selectedItem)">
                  {{ selectedItem.actions.positive.label }}
                </Button>
              </div>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Database, Brain, Server, CheckCircle, Plus, Bell, Users, Gauge, Calculator, Activity, AlertCircle, Info, Trash2, Home, User } from 'lucide-vue-next'
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
import { useInboxStore, type InboxItem } from '@/stores/inbox'

const inboxStore = useInboxStore()

// Mock transaction data - in a real app this would come from an API
const recentTransactions = ref([
  {
    id: 'TXN-2024-001',
    user: 'john.doe@company.com',
    endpoint: 'Financial-Analytics-API',
    status: 'Success',
    amount: '0.05',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000) // 2 hours ago
  },
  {
    id: 'TXN-2024-002',
    user: 'sarah.smith@contractor.com',
    endpoint: 'Customer-Insights',
    status: 'Success',
    amount: '0.12',
    timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000) // 4 hours ago
  },
  {
    id: 'TXN-2024-003',
    user: 'mike.johnson@partner.org',
    endpoint: 'Marketing-Data-API',
    status: 'Failed',
    amount: '0.08',
    timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000) // 6 hours ago
  },
  {
    id: 'TXN-2024-004',
    user: 'lisa.wong@university.edu',
    endpoint: 'Research-Dataset',
    status: 'Pending',
    amount: '0.03',
    timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000) // 8 hours ago
  },
  {
    id: 'TXN-2024-005',
    user: 'alex.chen@startup.com',
    endpoint: 'ML-Model-API',
    status: 'Success',
    amount: '0.25',
    timestamp: new Date(Date.now() - 12 * 60 * 60 * 1000) // 12 hours ago
  }
])

const selectedItem = ref<InboxItem | null>(null)
const dialogOpen = ref(false)

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
  // Policy-specific icons
  if (source === 'Human-in-the-Loop Policy') return Users
  if (source.includes('Rate Limiting')) return Gauge
  if (source === 'Accounting Policy') return Calculator
  if (source === 'OpenTelemetry Observability Policy') return Activity

  // Other source icons
  if (source.includes('Security')) return AlertCircle
  return Info
}

const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case 'success':
      return 'text-green-700 bg-green-50 border-green-200'
    case 'failed':
    case 'error':
      return 'text-red-700 bg-red-50 border-red-200'
    case 'pending':
      return 'text-yellow-700 bg-yellow-50 border-yellow-200'
    default:
      return 'text-gray-700 bg-gray-50 border-gray-200'
  }
}

const getSourceColor = (source: string) => {
  // Policy-specific colors
  if (source === 'Human-in-the-Loop Policy') return 'text-orange-600 bg-orange-100'
  if (source.includes('Rate Limiting')) return 'text-blue-600 bg-blue-100'
  if (source === 'Accounting Policy') return 'text-green-600 bg-green-100'
  if (source === 'OpenTelemetry Observability Policy') return 'text-purple-600 bg-purple-100'

  // Other source colors
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
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  })
}

// Enhanced markdown to HTML converter
function markdownToHtml(markdown: string): string {
  let html = markdown
    // Headers
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')

    // Bold and italic
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')

    // Code blocks with language hint
    .replace(/```(\w+)?\n([^`]+)```/g, '<pre><code>$2</code></pre>')
    .replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>')

    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')

    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-purple-600 hover:text-purple-700 underline">$1</a>')

    // Line breaks
    .replace(/\n\n/g, '</p><p>')

    // Lists - handle multi-line
    .split('\n')
    .map(line => {
      if (/^\d+\.\s/.test(line)) {
        return '<li>' + line.substring(line.indexOf('.') + 2) + '</li>'
      } else if (/^-\s/.test(line)) {
        return '<li>' + line.substring(2) + '</li>'
      }
      return line
    })
    .join('\n')

  // Wrap in paragraph tags
  html = '<p>' + html + '</p>'

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')

  // Wrap consecutive list items in ul/ol tags
  html = html.replace(/(<li>.*<\/li>\n?)+/g, match => {
    if (match.includes('<li>1.')) {
      return '<ol class="list-decimal list-inside space-y-1">' + match + '</ol>'
    }
    return '<ul class="list-disc list-inside space-y-1">' + match + '</ul>'
  })

  return html
}
</script>