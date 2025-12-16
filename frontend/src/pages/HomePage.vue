<template>
  <ErrorBoundary :can-retry="true" :show-details="true" custom-title="Dashboard Loading Error"
    custom-message="There was a problem loading the dashboard. Please try again." @retry="refreshDashboard">
    <div class="min-h-screen bg-background">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <!-- Hero Section -->
        <div class="text-left mb-16">
          <h1 class="heading-1 font-light text-foreground mb-4">
            Welcome to your
            <span class="font-medium text-primary">SyftAI Space</span>
          </h1>
          <p class="body-lg text-muted-foreground max-w-2xl">
            A Space where you can turn data and models into secure endpoints under your own rules for access, privacy, payments, and oversight.
          </p>
        </div>

        <!-- Action Cards -->
        <div class="mb-12">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="showCreateEndpointModal = true"
                    class="group bg-card hover:bg-muted rounded-xl p-6 text-left transition-all duration-200 border border-border hover:border-muted-foreground/20 hover:shadow-lg hover:-translate-y-1">
                    <div class="flex flex-col items-start space-y-3">
                      <div
                        class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <FolderOpen class="w-6 h-6 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <div class="font-medium text-foreground">
                          Publish your first data source
                        </div>
                        <div class="body-sm text-muted-foreground mt-1">
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
                  <button @click="$router.push('/datasets')"
                    class="group bg-card hover:bg-muted rounded-xl p-6 text-left transition-all duration-200 border border-border hover:border-muted-foreground/20 hover:shadow-lg hover:-translate-y-1">
                    <div class="flex flex-col items-start space-y-3">
                      <div
                        class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <Settings class="w-6 h-6 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <div class="font-medium text-foreground">Manage your data</div>
                        <div class="body-sm text-muted-foreground mt-1">Datasets and sources</div>
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
                  <button @click="$router.push('/models')"
                    class="group bg-card hover:bg-muted rounded-xl p-6 text-left transition-all duration-200 border border-border hover:border-muted-foreground/20 hover:shadow-lg hover:-translate-y-1">
                    <div class="flex flex-col items-start space-y-3">
                      <div
                        class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <Brain class="w-6 h-6 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <div class="font-medium text-foreground">Manage your models</div>
                        <div class="body-sm text-muted-foreground mt-1">
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
                  <button @click="$router.push('/inbox')"
                    class="group bg-card hover:bg-muted rounded-xl p-6 text-left transition-all duration-200 border border-border hover:border-muted-foreground/20 hover:shadow-lg hover:-translate-y-1 relative">
                    <div class="flex flex-col items-start space-y-3">
                      <div
                        class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <ShieldCheck class="w-6 h-6 text-orange-600 dark:text-orange-400" />
                      </div>
                      <div>
                        <div class="font-medium text-foreground">Review usage & requests</div>
                        <div class="body-sm text-muted-foreground mt-1">
                          {{ inboxStore.unreadCount }} pending
                        </div>
                      </div>
                    </div>
                    <div v-if="inboxStore.unreadCount > 0"
                      class="absolute -top-2 -right-2 w-3 h-3 bg-destructive rounded-full animate-pulse"></div>
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
        <div class="bg-card/80 backdrop-blur-sm rounded-xl border border-border p-4 mb-10 shadow-sm">
          <div class="flex items-center justify-center gap-8">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="$router.push('/datasets')"
                    class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted transition-colors">
                    <Database class="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    <span class="text-2xl font-light text-foreground">12</span>
                    <span class="body-sm text-muted-foreground">Datasets</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>View all datasets</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <div class="w-px h-8 bg-border"></div>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="$router.push('/models')"
                    class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted transition-colors">
                    <Brain class="w-4 h-4 text-purple-600 dark:text-purple-400" />
                    <span class="text-2xl font-light text-foreground">7</span>
                    <span class="body-sm text-muted-foreground">Models</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Manage AI models</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <div class="w-px h-8 bg-border"></div>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="$router.push('/inbox')"
                    class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted transition-colors">
                    <ShieldCheck class="w-4 h-4 text-orange-600 dark:text-orange-400" />
                    <span class="text-2xl font-light text-foreground">{{
                      inboxStore.unreadCount
                      }}</span>
                    <span class="body-sm text-muted-foreground">Requests</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Review pending requests</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <div class="w-px h-8 bg-border"></div>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button @click="revenueDialogOpen = true"
                    class="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted transition-colors">
                    <TrendingUp class="w-4 h-4 text-green-600 dark:text-green-400" />
                    <span class="text-2xl font-light text-foreground">${{ getTotalRevenue().total }}</span>
                    <span class="body-sm text-muted-foreground">Revenue</span>
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
        <div class="bg-card rounded-xl border border-border p-6 mb-10 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <h2 class="heading-3">Recent Activity</h2>
            <Button @click="$router.push('/inbox')" variant="ghost" size="sm"
              class="body-sm text-primary hover:text-primary/80">
              View all →
            </Button>
          </div>

          <div v-if="inboxStore.unreadCount === 0" class="text-center py-8">
            <p class="body-sm text-muted-foreground">No pending requests</p>
          </div>

          <div v-else class="space-y-3 max-h-64 overflow-y-auto">
            <div v-for="item in inboxStore.activeItems.slice(0, 3)" :key="item.id"
              class="flex items-start gap-3 p-4 rounded-lg bg-muted hover:bg-muted/80 cursor-pointer transition-colors"
              @click="openItemDialog(item)">
              <div
                :class="`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${getSourceColor(item.source)}`">
                <component :is="getSourceIcon(item.source)" class="w-4 h-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-2">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="body-sm font-medium text-foreground truncate">{{
                        item.source
                        }}</span>
                      <div v-if="!item.read" class="w-2 h-2 bg-primary rounded-full"></div>
                    </div>
                    <p class="body-sm text-foreground truncate mb-1">{{ item.title }}</p>
                    <p class="body-sm font-light text-muted-foreground">
                      {{ formatTimestamp(item.timestamp) }}
                    </p>
                  </div>
                  <div v-if="item.actions" class="flex items-center gap-1" @click.stop>
                    <Button v-if="item.actions.positive" size="sm" variant="outline"
                      @click="handlePositiveAction(item)">
                      {{ item.actions.positive.label }}
                    </Button>
                    <Button v-if="item.actions.negative" size="sm" variant="outline"
                      class="text-destructive hover:text-destructive" @click="handleNegativeAction(item)">
                      {{ item.actions.negative.label }}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Getting Started -->
        <div class="bg-muted/50 rounded-xl p-6 border border-border">
          <h3 class="heading-3 mb-4 flex items-center gap-2">
            <Zap class="w-4 h-4 text-blue-600 dark:text-blue-400" />
            Quick Start Guide
          </h3>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <button
              class="group flex items-center gap-3 p-3 bg-card rounded-lg border border-border hover:border-border/60 transition-colors">
              <FileText class="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <div class="text-left">
                <div class="body-sm font-medium text-foreground">Publish Documents</div>
                <div class="body-sm text-muted-foreground">Share PDFs securely</div>
              </div>
            </button>

            <button
              class="group flex items-center gap-3 p-3 bg-card rounded-lg border border-border hover:border-border/60 transition-colors">
              <Zap class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <div class="text-left">
                <div class="body-sm font-medium text-foreground">Connect AI Models</div>
                <div class="body-sm text-muted-foreground">Link AI endpoints</div>
              </div>
            </button>

            <button
              class="group flex items-center gap-3 p-3 bg-card rounded-lg border border-border hover:border-border/60 transition-colors">
              <Shield class="w-4 h-4 text-purple-600 dark:text-purple-400" />
              <div class="text-left">
                <div class="body-sm font-medium text-foreground">Configure Access</div>
                <div class="body-sm text-muted-foreground">Set permissions</div>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- Item Detail Dialog -->
      <Dialog v-model:open="dialogOpen">
        <DialogContent v-if="selectedItem"
          class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl">
          <div class="flex-shrink-0 border-b bg-muted/50">
            <DialogHeader class="p-6 pb-4">
              <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3">
                  <div :class="`p-3 rounded-lg ${getSourceColor(selectedItem.source)}`">
                    <component :is="getSourceIcon(selectedItem.source)" class="h-5 w-5" />
                  </div>
                  <div>
                    <div class="flex items-center gap-2 mb-1">
                      <Badge variant="outline" class="body-sm">{{ selectedItem.source }}</Badge>
                      <div v-if="!selectedItem.read" class="flex items-center gap-1 body-sm text-primary">
                        <div class="w-2 h-2 bg-primary rounded-full"></div>
                        <span>New</span>
                      </div>
                    </div>
                    <span class="body-sm text-muted-foreground">
                      {{ formatTimestamp(selectedItem.timestamp) }}
                    </span>
                  </div>
                </div>
              </div>
              <DialogTitle class="heading-2">{{ selectedItem.title }}</DialogTitle>
              <DialogDescription class="mt-2 body-base">{{
                selectedItem.summary
                }}</DialogDescription>
            </DialogHeader>
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto">
            <div class="p-6">
              <div
                class="prose prose-sm max-w-none prose-headings:font-semibold prose-h2:text-lg prose-h3:text-base prose-p:text-muted-foreground prose-strong:text-foreground prose-code:text-primary prose-code:font-mono prose-pre:bg-muted prose-pre:border prose-pre:font-mono prose-li:text-muted-foreground dark:prose-invert"
                v-html="markdownToHtml(selectedItem.longDescription)" />
            </div>
          </div>

          <div class="flex-shrink-0 border-t bg-muted/50">
            <DialogFooter class="p-6 pt-4">
              <div class="flex items-center justify-between w-full">
                <div class="flex items-center gap-4">
                  <Button variant="ghost" size="default" class="text-muted-foreground hover:text-foreground" @click="
                    () => {
                      selectedItem && dismissItem(selectedItem)
                      dialogOpen = false
                    }
                  ">
                    <Trash2 class="h-4 w-4 mr-2" />
                    Dismiss
                  </Button>
                </div>
                <div class="flex items-center gap-3">
                  <Button v-if="selectedItem.actions?.negative" variant="outline" size="default"
                    @click="selectedItem && handleNegativeAction(selectedItem)">
                    {{ selectedItem.actions.negative.label }}
                  </Button>
                  <Button v-if="selectedItem.actions?.positive" variant="default" size="default"
                    @click="selectedItem && handlePositiveAction(selectedItem)">
                    {{ selectedItem.actions.positive.label }}
                  </Button>
                </div>
              </div>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      <!-- Revenue Details Dialog -->
      <RevenueDetailsDialog v-model:open="revenueDialogOpen" />
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useInboxStore, type InboxItem } from '@/stores/inbox'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import CreateEndpointModal from '@/components/CreateEndpointModal.vue'
import RevenueDetailsDialog from '@/components/RevenueDetailsDialog.vue'
import { getTotalRevenue } from '@/composables/useRevenue'

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
  if (source === 'Human-in-the-Loop Policy')
    return 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-950/50'
  if (source.includes('Rate Limiting'))
    return 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50'
  if (source === 'Accounting Policy')
    return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/50'
  if (source === 'OpenTelemetry Observability Policy') return 'text-primary bg-primary/10'
  if (source.includes('Security')) return 'text-destructive bg-destructive/10'
  if (source.includes('Update'))
    return 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50'
  if (source.includes('Usage')) return 'text-primary bg-primary/10'
  return 'text-muted-foreground bg-muted'
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
      '<a href="$2" class="text-primary hover:text-primary/80 underline">$1</a>',
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
