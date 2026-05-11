<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import {
  MessageSquare,
  Send,
  Trash2,
  Database,
  Brain,
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Sparkles,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import VueMarkdown from 'vue-markdown-render'
import { useEndpointsStore } from '@/stores/endpoints'
import { useEndpointChat } from '@/composables/useEndpointChat'
import { useNavigation } from '@/composables/useNavigation'
import type { EndpointItem } from '@/stores/endpoints'

const { turns, loading, error, sendMessage, clearChat } = useEndpointChat()
const { goToGoLive } = useNavigation()
const endpointsStore = useEndpointsStore()

const endpointSlug = ref<string | null>(null)
const dataSourceSlugs = ref<string[]>([])
const inputText = ref('')
const messagesEndRef = ref<HTMLElement | null>(null)
const expandedRefs = ref<Set<number>>(new Set())

const isModelEndpoint = (e: EndpointItem) => !!e.modelId && !e.datasetId
const isDataEndpoint = (e: EndpointItem) => !!e.datasetId && !e.modelId

const modelEndpoints = computed(() => endpointsStore.endpoints.filter(isModelEndpoint))
const dataEndpoints = computed(() => endpointsStore.endpoints.filter(isDataEndpoint))

const hasNoModelEndpoints = computed(
  () => !endpointsStore.isLoading && modelEndpoints.value.length === 0,
)

const selectedEndpoint = computed(
  () => modelEndpoints.value.find((e) => e.slug === endpointSlug.value) ?? null,
)

watch(modelEndpoints, (list) => {
  if (endpointSlug.value && !list.some((e) => e.slug === endpointSlug.value)) {
    endpointSlug.value = null
  }
})

watch(dataEndpoints, (list) => {
  const available = new Set(list.map((e) => e.slug))
  dataSourceSlugs.value = dataSourceSlugs.value.filter((slug) => available.has(slug))
})

function toggleDataSource(slug: string, checked: boolean) {
  if (checked) {
    if (!dataSourceSlugs.value.includes(slug)) {
      dataSourceSlugs.value = [...dataSourceSlugs.value, slug]
    }
  } else {
    dataSourceSlugs.value = dataSourceSlugs.value.filter((s) => s !== slug)
  }
}

const canSubmit = computed(
  () => inputText.value.trim().length > 0 && selectedEndpoint.value != null && !loading.value,
)

onMounted(() => {
  endpointsStore.fetchEndpoints()
})

watch(
  () => turns.value.length,
  () => {
    nextTick(() => {
      messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
    })
  },
)

async function handleSend() {
  if (!canSubmit.value || !endpointSlug.value) return

  const text = inputText.value.trim()
  inputText.value = ''

  await sendMessage({ content: text, endpointSlug: endpointSlug.value })
}

function isDialogOpen(): boolean {
  return document.querySelector('[role="dialog"][data-state="open"]') !== null
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.shiftKey) return
  if (isDialogOpen()) return
  e.preventDefault()
  handleSend()
}

function toggleRefs(index: number) {
  if (expandedRefs.value.has(index)) {
    expandedRefs.value.delete(index)
  } else {
    expandedRefs.value.add(index)
  }
}

function handleClear() {
  clearChat()
  expandedRefs.value.clear()
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Messages Area -->
    <ScrollArea class="flex-1">
      <div class="max-w-3xl mx-auto px-6 py-6">
        <!-- No Model Endpoints Available State -->
        <div
          v-if="hasNoModelEndpoints && turns.length === 0"
          class="flex flex-col items-center justify-center py-24"
        >
          <Alert class="max-w-md">
            <Sparkles class="h-4 w-4" />
            <AlertTitle>No model APIs published yet</AlertTitle>
            <AlertDescription>
              <p class="mb-3">
                Publish a model API first — this chat tests it exactly as your users will experience
                it, including all your access rules, usage limits, and filters.
              </p>
              <Button size="sm" @click="goToGoLive"> Publish your first API </Button>
            </AlertDescription>
          </Alert>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="turns.length === 0 && !loading"
          class="flex flex-col items-center justify-center py-24 text-center"
        >
          <MessageSquare class="h-12 w-12 text-muted-foreground/40 mb-6" />
          <h2 class="text-xl font-semibold text-foreground mb-2">Test your APIs</h2>
          <p class="text-sm text-muted-foreground max-w-md">
            Select a model below, optionally attach data sources, and send a message. You'll get the
            exact same response your users do — policies, filters, and all.
          </p>
        </div>

        <!-- Conversation -->
        <div v-else class="space-y-6">
          <div v-for="(turn, idx) in turns" :key="idx">
            <!-- User Message -->
            <div v-if="turn.role === 'user'" class="flex justify-end">
              <div
                class="bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%]"
              >
                <p class="text-sm whitespace-pre-wrap">{{ turn.content }}</p>
              </div>
            </div>

            <!-- Assistant Message -->
            <div v-else class="flex flex-col gap-2">
              <div class="bg-muted/50 rounded-2xl rounded-bl-md px-4 py-3 max-w-[90%]">
                <div class="prose prose-sm dark:prose-invert max-w-none text-foreground">
                  <VueMarkdown :source="turn.content" :options="{ linkify: true, breaks: true }" />
                </div>

                <!-- Token Usage -->
                <div v-if="turn.summary" class="mt-2 pt-2 border-t border-border/50">
                  <span class="text-xs text-muted-foreground">
                    {{ turn.summary.model }} &middot; {{ turn.summary.usage.total_tokens }} tokens
                  </span>
                </div>
              </div>

              <!-- References -->
              <div
                v-if="turn.role === 'assistant' && turn.references?.documents?.length"
                class="max-w-[90%]"
              >
                <button
                  class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors py-1"
                  @click="toggleRefs(idx)"
                >
                  <ChevronDown v-if="expandedRefs.has(idx)" class="h-3.5 w-3.5" />
                  <ChevronRight v-else class="h-3.5 w-3.5" />
                  {{ turn.references.documents.length }} source{{
                    turn.references.documents.length !== 1 ? 's' : ''
                  }}
                  <Badge
                    v-if="turn.references.search_engine"
                    variant="secondary"
                    class="text-[10px] ml-1 px-1.5 py-0"
                  >
                    {{ turn.references.search_engine }}
                  </Badge>
                </button>
                <div v-if="expandedRefs.has(idx)" class="space-y-2 mt-1 pl-5">
                  <div
                    v-for="(doc, docIdx) in turn.references.documents"
                    :key="docIdx"
                    class="border border-border/50 rounded-lg p-3 bg-card"
                  >
                    <div class="flex items-start gap-2">
                      <FileText class="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="text-xs font-medium text-foreground truncate">
                            {{ doc.document_id }}
                          </span>
                          <Badge variant="outline" class="text-[10px] px-1.5 py-0 shrink-0">
                            {{ (doc.similarity_score * 100).toFixed(0) }}%
                          </Badge>
                        </div>
                        <p class="text-xs text-muted-foreground line-clamp-3">
                          {{ doc.content }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Loading indicator -->
          <div v-if="loading" class="flex items-center gap-2 text-muted-foreground">
            <Loader2 class="h-4 w-4 animate-spin" />
            <span class="text-sm">Thinking...</span>
          </div>
        </div>

        <!-- Error -->
        <Alert v-if="error" variant="destructive" class="mt-4">
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <div ref="messagesEndRef" />
      </div>
    </ScrollArea>

    <!-- Input Area -->
    <div class="shrink-0 px-6 py-3">
      <div class="max-w-3xl mx-auto">
        <div
          class="flex flex-col rounded-3xl border border-border bg-background dark:bg-input/30 shadow-sm transition-shadow focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30"
        >
          <Textarea
            v-model="inputText"
            :placeholder="
              hasNoModelEndpoints
                ? 'Publish a model API to start testing'
                : selectedEndpoint
                  ? 'Ask a question...'
                  : 'Select a model to start testing'
            "
            :disabled="!selectedEndpoint"
            class="resize-none min-h-[76px] max-h-[192px] border-0 shadow-none bg-transparent dark:bg-transparent rounded-3xl px-5 pt-4 pb-2 focus-visible:ring-0 focus-visible:border-0"
            rows="2"
            @keydown="handleKeydown"
          />

          <div class="flex items-center justify-between gap-2 px-3 pb-3">
            <!-- Left: data sources multi-select + clear -->
            <div class="flex items-center gap-2">
              <DropdownMenu :modal="false">
                <DropdownMenuTrigger as-child>
                  <Button
                    variant="outline"
                    size="sm"
                    class="h-8 gap-1.5 px-2.5 text-xs font-normal border-border/60 bg-muted/40 hover:bg-muted/70 rounded-full"
                  >
                    <Database class="h-3 w-3 text-muted-foreground" />
                    <span>
                      {{
                        dataSourceSlugs.length === 0
                          ? 'Data sources'
                          : `Data sources · ${dataSourceSlugs.length}`
                      }}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" class="min-w-[240px]">
                  <DropdownMenuLabel>Attach data sources</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <div
                    v-if="dataEndpoints.length === 0"
                    class="px-2 py-1.5 text-xs text-muted-foreground"
                  >
                    No data endpoints published
                  </div>
                  <DropdownMenuCheckboxItem
                    v-for="endpoint in dataEndpoints"
                    :key="endpoint.id"
                    :model-value="dataSourceSlugs.includes(endpoint.slug)"
                    @update:model-value="(checked) => toggleDataSource(endpoint.slug, checked)"
                    @select.prevent
                  >
                    <span class="truncate">{{ endpoint.name }}</span>
                  </DropdownMenuCheckboxItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <TooltipProvider v-if="turns.length > 0" :delay-duration="0">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-8 w-8 shrink-0 rounded-full"
                      @click="handleClear"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Clear conversation</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            <!-- Right: model selector + send -->
            <div class="flex items-center gap-2">
              <Select v-model="endpointSlug">
                <SelectTrigger
                  class="w-auto h-8 gap-1.5 px-2.5 text-xs border-border/60 bg-muted/40 hover:bg-muted/70 transition-colors rounded-full"
                >
                  <Brain class="h-3 w-3 text-muted-foreground shrink-0" />
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  <div
                    v-if="modelEndpoints.length === 0"
                    class="px-2 py-1.5 text-xs text-muted-foreground"
                  >
                    No model endpoints published
                  </div>
                  <SelectItem
                    v-for="endpoint in modelEndpoints"
                    :key="endpoint.id"
                    :value="endpoint.slug"
                  >
                    <div class="flex items-center gap-2">
                      <Brain class="h-3 w-3 text-muted-foreground shrink-0" />
                      <span>{{ endpoint.name }}</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              <Button
                :disabled="!canSubmit"
                size="icon"
                class="h-8 w-8 rounded-full shrink-0"
                @click="handleSend"
              >
                <Send class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
