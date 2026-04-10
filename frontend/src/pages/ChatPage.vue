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
import { Alert, AlertDescription } from '@/components/ui/alert'
import { modelsApi } from '@/api/endpoints/models'
import { datasetsApi } from '@/api/endpoints/datasets'
import { useLocalChat, type ChatTurn } from '@/composables/useLocalChat'
import type { ModelListItem, DatasetListItem } from '@/api/types'

const { turns, loading, error, modelId, datasetId, sendMessage, clearChat } = useLocalChat()

const models = ref<ModelListItem[]>([])
const datasets = ref<DatasetListItem[]>([])
const modelsLoading = ref(true)
const datasetsLoading = ref(true)
const inputText = ref('')
const messagesEndRef = ref<HTMLElement | null>(null)
const expandedRefs = ref<Set<number>>(new Set())

const canSend = computed(() => modelId.value && inputText.value.trim() && !loading.value)

onMounted(async () => {
  const [modelsList, datasetsList] = await Promise.all([
    modelsApi.list().finally(() => (modelsLoading.value = false)),
    datasetsApi.list().finally(() => (datasetsLoading.value = false)),
  ])
  models.value = modelsList
  datasets.value = datasetsList
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
  if (!canSend.value) return
  const text = inputText.value.trim()
  inputText.value = ''
  await sendMessage(text)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
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

function isAssistant(turn: ChatTurn) {
  return turn.role === 'assistant'
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Messages Area -->
    <ScrollArea class="flex-1">
      <div class="max-w-3xl mx-auto px-6 py-6">
        <!-- Empty State -->
        <div
          v-if="turns.length === 0 && !loading"
          class="flex flex-col items-center justify-center py-24 text-center"
        >
          <MessageSquare class="h-12 w-12 text-muted-foreground/40 mb-6" />
          <h2 class="text-xl font-semibold text-foreground mb-2">Test your resources</h2>
          <p class="text-sm text-muted-foreground max-w-md">
            Select a model and optionally a data source below, then ask a question to test whether
            your resources are working correctly.
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
                v-if="isAssistant(turn) && turn.references?.documents?.length"
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

    <!-- Input Area (includes selectors) -->
    <div class="shrink-0 border-t border-border px-6 py-3">
      <div class="max-w-3xl mx-auto flex flex-col gap-2">
        <!-- Selectors row -->
        <div class="flex items-center gap-2 flex-wrap">
          <Select v-model="modelId">
            <SelectTrigger
              class="w-auto h-7 gap-1.5 px-2.5 text-xs border-border/60 bg-muted/40 hover:bg-muted/70 transition-colors rounded-full"
            >
              <Brain class="h-3 w-3 text-muted-foreground shrink-0" />
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="m in models" :key="m.id" :value="m.id">
                {{ m.name }}
              </SelectItem>
            </SelectContent>
          </Select>

          <Select v-model="datasetId">
            <SelectTrigger
              class="w-auto h-7 gap-1.5 px-2.5 text-xs border-border/60 bg-muted/40 hover:bg-muted/70 transition-colors rounded-full"
            >
              <Database class="h-3 w-3 text-muted-foreground shrink-0" />
              <SelectValue placeholder="Select context" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="null as unknown as string"> None </SelectItem>
              <SelectItem v-for="d in datasets" :key="d.id" :value="d.id">
                {{ d.name }}
              </SelectItem>
            </SelectContent>
          </Select>

          <TooltipProvider v-if="turns.length > 0" :delay-duration="0">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0" @click="handleClear">
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Clear conversation</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        <!-- Text input + send -->
        <div class="flex gap-3">
          <Textarea
            v-model="inputText"
            :placeholder="modelId ? 'Ask a question...' : 'Select a model to start chatting'"
            :disabled="!modelId"
            class="resize-none min-h-[44px] max-h-[120px]"
            rows="1"
            @keydown="handleKeydown"
          />
          <Button :disabled="!canSend" class="shrink-0 self-end" @click="handleSend">
            <Send class="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
