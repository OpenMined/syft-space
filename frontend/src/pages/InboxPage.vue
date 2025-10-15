<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Inbox,
  X,
  AlertCircle,
  Info,
  Trash2,
  Users,
  Gauge,
  Calculator,
  Activity,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
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

const selectedItem = ref<InboxItem | null>(null)
const dialogOpen = ref(false)
const activeTab = ref('all')

const activeItems = computed(() => {
  const nonDismissed = inboxStore.activeItems

  let filtered = nonDismissed
  if (activeTab.value === 'read') {
    filtered = nonDismissed.filter((item) => item.read)
  } else if (activeTab.value === 'unread') {
    filtered = nonDismissed.filter((item) => !item.read)
  }

  return filtered
})

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
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <Inbox class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Inbox</h1>
      <Badge
        v-if="inboxStore.unreadCount > 0"
        variant="secondary"
        class="bg-purple-100 text-purple-700"
      >
        {{ inboxStore.unreadCount }} new
      </Badge>
    </div>
    <p class="text-gray-600 mb-8">Review notifications, policy decisions, and system alerts</p>

    <!-- Tabs -->
    <Tabs v-model="activeTab" class="w-full mb-8">
      <TabsList
        class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]"
      >
        <TabsTrigger value="all">All</TabsTrigger>
        <TabsTrigger value="unread">Unread</TabsTrigger>
        <TabsTrigger value="read">Read</TabsTrigger>
      </TabsList>
    </Tabs>

    <!-- Empty State -->
    <div v-if="activeItems.length === 0" class="text-center py-12">
      <Inbox class="mx-auto h-12 w-12 text-gray-400" />
      <h3 class="mt-2 text-sm font-semibold text-gray-900">No items</h3>
      <p class="mt-1 text-sm text-gray-500">Your inbox is empty.</p>
    </div>

    <!-- Inbox Items -->
    <div v-else class="space-y-4">
      <Card
        v-for="item in activeItems"
        :key="item.id"
        class="cursor-pointer hover:shadow-md transition-shadow"
        :class="{ 'border-purple-200 bg-purple-50/50': !item.read }"
        @click="openItemDialog(item)"
      >
        <CardHeader class="pb-3">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3 flex-1">
              <div :class="`p-2 rounded-lg ${getSourceColor(item.source)}`">
                <component :is="getSourceIcon(item.source)" class="h-4 w-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <Badge variant="outline" class="text-xs">{{ item.source }}</Badge>
                  <span class="text-xs text-gray-500">
                    {{ item.timestamp.toLocaleString() }}
                  </span>
                  <div v-if="!item.read" class="w-2 h-2 bg-purple-500 rounded-full"></div>
                </div>
                <CardTitle class="text-base">{{ item.title }}</CardTitle>
                <CardDescription class="mt-1">{{ item.summary }}</CardDescription>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <!-- Action Buttons -->
              <div v-if="item.actions" class="flex items-center gap-2">
                <Button
                  v-if="item.actions.positive"
                  size="sm"
                  variant="default"
                  class="h-8 text-xs"
                  @click.stop="handlePositiveAction(item)"
                >
                  {{ item.actions.positive.label }}
                </Button>
                <Button
                  v-if="item.actions.negative"
                  size="sm"
                  variant="outline"
                  class="h-8 text-xs"
                  @click.stop="handleNegativeAction(item)"
                >
                  {{ item.actions.negative.label }}
                </Button>
              </div>
              <!-- Dismiss Button -->
              <Button
                variant="ghost"
                size="sm"
                class="h-8 w-8 p-0 ml-2"
                @click.stop="dismissItem(item)"
              >
                <X class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>
    </div>

    <!-- Item Detail Dialog -->
    <Dialog v-model:open="dialogOpen">
      <DialogContent
        v-if="selectedItem"
        class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl"
      >
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
            <DialogTitle class="text-xl font-semibold">{{ selectedItem.title }}</DialogTitle>
            <DialogDescription class="mt-2 text-base">{{ selectedItem.summary }}</DialogDescription>
          </DialogHeader>
        </div>

        <!-- Content -->
        <div class="flex-1 min-h-0 overflow-y-auto">
          <div class="p-6">
            <div
              class="prose prose-sm max-w-none prose-headings:font-semibold prose-h2:text-lg prose-h3:text-base prose-p:text-gray-600 prose-strong:text-gray-900 prose-code:text-purple-600 prose-pre:bg-gray-50 prose-pre:border prose-li:text-gray-600"
              v-html="markdownToHtml(selectedItem.longDescription)"
            />
          </div>
        </div>

        <!-- Footer with actions -->
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
  </div>
</template>

<script lang="ts">
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
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" class="text-purple-600 hover:text-purple-700 underline">$1</a>',
    )

    // Line breaks
    .replace(/\n\n/g, '</p><p>')

    // Lists - handle multi-line
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

  // Wrap in paragraph tags
  html = '<p>' + html + '</p>'

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')

  // Wrap consecutive list items in ul/ol tags
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => {
    if (match.includes('<li>1.')) {
      return '<ol class="list-decimal list-inside space-y-1">' + match + '</ol>'
    }
    return '<ul class="list-disc list-inside space-y-1">' + match + '</ul>'
  })

  return html
}
</script>
