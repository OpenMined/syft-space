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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useEndpointsStore } from '@/stores/endpoints'
import { useLocalChat } from '@/composables/useLocalChat'
import { useNavigation } from '@/composables/useNavigation'

const { turns, loading, error, sendMessage, clearChat } = useLocalChat()
const { goToGoLive } = useNavigation()
const endpointsStore = useEndpointsStore()

const modelApiSlug = ref<string | null>(null)
const dataApiSlug = ref<string | null>(null)
const inputText = ref('')
const messagesEndRef = ref<HTMLElement | null>(null)
const expandedRefs = ref<Set<number>>(new Set())

const modelApis = computed(() => endpointsStore.endpoints.filter((e) => e.modelId != null))
const dataApis = computed(() => endpointsStore.endpoints.filter((e) => e.datasetId != null))

const selectedModelApi = computed(
  () => modelApis.value.find((e) => e.slug === modelApiSlug.value) ?? null,
)
const selectedDataApi = computed(
  () => dataApis.value.find((e) => e.slug === dataApiSlug.value) ?? null,
)

const hasNoModelApis = computed(
  () => !endpointsStore.isLoading && modelApis.value.length === 0,
)
const canSubmit = computed(
  () => inputText.value.trim().length > 0 && selectedModelApi.value != null && !loading.value,
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
  if (!canSubmit.value || !selectedModelApi.value) return
  const modelId = selectedModelApi.value.modelId
  if (!modelId) return

  const text = inputText.value.trim()
  inputText.value = ''

  await sendMessage({
    content: text,
    modelId,
    datasetId: selectedDataApi.value?.datasetId ?? null,
    systemPrompt: selectedModelApi.value.systemPrompt ?? null,
  })
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
        <!-- No Model APIs Available State -->
        <div
          v-if="hasNoModelApis && turns.length === 0"
          class="flex flex-col items-center justify-center py-24"
        >
          <Alert class="max-w-md">
            <Sparkles class="h-4 w-4" />
            <AlertTitle>No APIs with a model yet</AlertTitle>
            <AlertDescription>
              <p class="mb-3">
                Publish an API that has a model attached before you can test it in chat.
              </p>
              <Button size="sm" @click="goToGoLive"> Go live with an API </Button>
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
            Pick an API with a model, optionally attach a data source API for context, then ask a
            question to test whether your setup is working.
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
                <p class="text-sm text-foreground whitespace-pre-wrap">{{ turn.content }}</p>

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

    <!-- Input Area (selectors + send fused inside the prompt) -->
    <div class="shrink-0 px-6 py-3">
      <div class="max-w-3xl mx-auto">
        <div
          class="flex flex-col rounded-3xl border border-border bg-background dark:bg-input/30 shadow-sm transition-shadow focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30"
        >
          <Textarea
            v-model="inputText"
            :placeholder="
              hasNoModelApis
                ? 'Publish a model API to start chatting'
                : selectedModelApi
                  ? 'Ask a question...'
                  : 'Select a model API to start chatting'
            "
            :disabled="!selectedModelApi"
            class="resize-none min-h-[76px] max-h-[192px] border-0 shadow-none bg-transparent dark:bg-transparent rounded-3xl px-5 pt-4 pb-2 focus-visible:ring-0 focus-visible:border-0"
            rows="2"
            @keydown="handleKeydown"
          />

          <div class="flex items-center justify-between gap-2 px-3 pb-3">
            <!-- Left: data API dropdown + clear -->
            <div class="flex items-center gap-2">
              <Select v-model="dataApiSlug" :disabled="dataApis.length === 0">
                <SelectTrigger
                  class="w-auto h-8 gap-1.5 px-2.5 text-xs border-border/60 bg-muted/40 hover:bg-muted/70 transition-colors rounded-full"
                >
                  <Database class="h-3 w-3 text-muted-foreground shrink-0" />
                  <SelectValue placeholder="Add context" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="api in dataApis" :key="api.id" :value="api.slug">
                    {{ api.name }}
                  </SelectItem>
                </SelectContent>
              </Select>

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

            <!-- Right: model dropdown + send -->
            <div class="flex items-center gap-2">
              <Select v-model="modelApiSlug">
                <SelectTrigger
                  class="w-auto h-8 gap-1.5 px-2.5 text-xs border-border/60 bg-muted/40 hover:bg-muted/70 transition-colors rounded-full"
                >
                  <Brain class="h-3 w-3 text-muted-foreground shrink-0" />
                  <SelectValue placeholder="Select model API" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="api in modelApis" :key="api.id" :value="api.slug">
                    {{ api.name }}
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
