<template>
  <ErrorBoundary
    :can-retry="true"
    :show-details="true"
    custom-title="Dashboard Loading Error"
    custom-message="There was a problem loading the dashboard. Please try again."
    @retry="refreshDashboard"
  >
    <div class="min-h-screen">
      <!-- Hero with gradient glow -->
      <div class="relative overflow-hidden">
        <div class="absolute inset-0 -z-10 opacity-30 dark:opacity-20 blur-3xl" aria-hidden="true">
          <div class="absolute top-[-10%] left-[10%] h-72 w-72 rounded-full bg-primary/40" />
          <div
            class="absolute top-[5%] right-[15%] h-56 w-56 rounded-full bg-cyan-400/30 dark:bg-cyan-500/20"
          />
          <div
            class="absolute top-[20%] left-[40%] h-48 w-48 rounded-full bg-teal-300/20 dark:bg-teal-600/15"
          />
        </div>

        <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-12">
          <div class="mb-12">
            <h1
              class="text-4xl sm:text-5xl font-semibold tracking-tight text-foreground mb-4 leading-[1.1]"
            >
              Your space to share
              <span
                class="bg-gradient-to-r from-primary via-teal-500 to-cyan-500 dark:from-primary dark:via-teal-400 dark:to-cyan-400 bg-clip-text text-transparent"
                >knowledge</span
              >
            </h1>
            <p class="text-lg text-muted-foreground max-w-md leading-relaxed">
              Publish documents and AI models on your terms. Set a fair price. See your contribution
              recognized.
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <Button
              @click="router.push({ name: 'go-live' })"
              size="lg"
              class="px-6 h-12 text-[15px] font-medium shadow-md hover:shadow-lg transition-all"
            >
              <Zap class="w-4 h-4 mr-2" />
              Publish
            </Button>
            <Button
              variant="outline"
              size="lg"
              class="h-12 px-5 text-[15px]"
              @click="router.push({ name: 'datasets' })"
            >
              <FileText class="w-4 h-4 mr-2" />
              Data Sources
            </Button>
            <Button
              variant="outline"
              size="lg"
              class="h-12 px-5 text-[15px]"
              @click="router.push({ name: 'models' })"
            >
              <Brain class="w-4 h-4 mr-2" />
              Models
            </Button>
            <Button
              variant="outline"
              size="lg"
              class="h-12 px-5 text-[15px]"
              @click="router.push({ name: 'settings' })"
            >
              <BarChart3 class="w-4 h-4 mr-2" />
              Analytics
            </Button>
          </div>
        </div>
      </div>

      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
        <!-- Your APIs -->
        <div class="rounded-xl border border-border/50 bg-card mb-12">
          <div class="flex items-center justify-between px-5 py-4 border-b border-border/50">
            <h2 class="text-sm font-semibold text-foreground">Your APIs</h2>
            <button
              @click="router.push({ name: 'endpoints' })"
              class="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              View all
            </button>
          </div>

          <!-- Loading -->
          <div v-if="endpointsStore.isLoading" class="p-5 space-y-3">
            <div v-for="i in 3" :key="i" class="flex items-center gap-3">
              <Skeleton class="h-2 w-2 rounded-full" />
              <Skeleton class="h-4 flex-1 max-w-48" />
              <Skeleton class="h-3 w-16" />
            </div>
          </div>

          <!-- Empty State -->
          <div v-else-if="endpointsStore.endpoints.length === 0" class="px-5 py-10 text-center">
            <div class="p-3 rounded-full bg-primary/10 w-fit mx-auto mb-3">
              <Radio class="w-5 h-5 text-primary" />
            </div>
            <p class="text-sm text-muted-foreground mb-4">
              No APIs yet. Publish your first resource.
            </p>
            <Button variant="outline" size="sm" @click="router.push({ name: 'go-live' })">
              <Zap class="w-3.5 h-3.5 mr-1.5" />
              Publish
            </Button>
          </div>

          <!-- API List -->
          <div v-else class="divide-y divide-border/40">
            <button
              v-for="ep in recentEndpoints"
              :key="ep.id"
              class="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-muted/40 transition-colors"
              @click="router.push({ name: 'endpoint-detail', params: { id: ep.id } })"
            >
              <div
                :class="
                  ep.published
                    ? 'w-2 h-2 rounded-full bg-green-500 shrink-0'
                    : 'w-2 h-2 rounded-full bg-muted-foreground/30 shrink-0'
                "
              />
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-foreground truncate">{{ ep.name }}</div>
                <div class="text-xs text-muted-foreground truncate">
                  {{ ep.dataSourceType || ep.modelType || 'API' }}
                </div>
              </div>
              <div class="text-[11px] text-muted-foreground shrink-0">
                {{ ep.published ? 'Published' : 'Draft' }}
              </div>
            </button>
          </div>
        </div>

        <!-- Quick Start -->
        <div>
          <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
            Get started
          </h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <a
              href="http://syft.docs.openmined.org/space/quickstart"
              target="_blank"
              rel="noopener noreferrer"
              class="group flex items-center gap-3 p-3.5 rounded-lg border border-transparent hover:border-border/50 hover:bg-card transition-all"
            >
              <div
                class="p-2 rounded-lg bg-green-500/10 group-hover:bg-green-500/15 transition-colors"
              >
                <Zap class="w-4 h-4 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <div class="text-sm font-medium text-foreground">Quickstart</div>
                <div class="text-xs text-muted-foreground">Get up and running in 5 minutes</div>
              </div>
            </a>
            <a
              href="http://syft.docs.openmined.org/space/components/datasets"
              target="_blank"
              rel="noopener noreferrer"
              class="group flex items-center gap-3 p-3.5 rounded-lg border border-transparent hover:border-border/50 hover:bg-card transition-all"
            >
              <div
                class="p-2 rounded-lg bg-blue-500/10 group-hover:bg-blue-500/15 transition-colors"
              >
                <FileText class="w-4 h-4 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <div class="text-sm font-medium text-foreground">Publish Documents</div>
                <div class="text-xs text-muted-foreground">Share PDFs and datasets securely</div>
              </div>
            </a>
            <a
              href="http://syft.docs.openmined.org/space/components/models"
              target="_blank"
              rel="noopener noreferrer"
              class="group flex items-center gap-3 p-3.5 rounded-lg border border-transparent hover:border-border/50 hover:bg-card transition-all"
            >
              <div
                class="p-2 rounded-lg bg-indigo-500/10 group-hover:bg-indigo-500/15 transition-colors"
              >
                <Brain class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div>
                <div class="text-sm font-medium text-foreground">Connect AI Models</div>
                <div class="text-xs text-muted-foreground">Link your vLLM models</div>
              </div>
            </a>
            <a
              href="http://syft.docs.openmined.org/space/components/policies"
              target="_blank"
              rel="noopener noreferrer"
              class="group flex items-center gap-3 p-3.5 rounded-lg border border-transparent hover:border-border/50 hover:bg-card transition-all"
            >
              <div
                class="p-2 rounded-lg bg-purple-500/10 group-hover:bg-purple-500/15 transition-colors"
              >
                <Shield class="w-4 h-4 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <div class="text-sm font-medium text-foreground">Configure Policies</div>
                <div class="text-xs text-muted-foreground">Rate limits, pricing, and access</div>
              </div>
            </a>
          </div>
        </div>
      </div>

      <!-- Item Detail Dialog -->
      <Dialog v-model:open="dialogOpen">
        <DialogContent
          v-if="selectedItem"
          class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl"
        >
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
                      <div
                        v-if="!selectedItem.read"
                        class="flex items-center gap-1 body-sm text-primary"
                      >
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
                v-html="markdownToHtml(selectedItem.longDescription)"
              />
            </div>
          </div>

          <div class="flex-shrink-0 border-t bg-muted/50">
            <DialogFooter class="p-6 pt-4">
              <div class="flex items-center justify-between w-full">
                <div class="flex items-center gap-4">
                  <Button
                    variant="ghost"
                    size="default"
                    class="text-muted-foreground hover:text-foreground"
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
  </ErrorBoundary>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Brain,
  Users,
  Gauge,
  Calculator,
  Activity,
  AlertCircle,
  Info,
  Trash2,
  FileText,
  Zap,
  Shield,
  Radio,
  BarChart3,
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
import { useInboxStore, type InboxItem } from '@/stores/inbox'
import { useEndpointsStore } from '@/stores/endpoints'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import { Skeleton } from '@/components/ui/skeleton'

const router = useRouter()
const inboxStore = useInboxStore()
const endpointsStore = useEndpointsStore()

const recentEndpoints = computed(() => endpointsStore.endpoints.slice(0, 5))

onMounted(() => {
  endpointsStore.fetchEndpoints()
})

const selectedItem = ref<InboxItem | null>(null)
const dialogOpen = ref(false)

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
