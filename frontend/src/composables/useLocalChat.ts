import { ref, onBeforeUnmount } from 'vue'
import { chatApi } from '@/api/endpoints/chat'
import type {
  LocalChatMessage,
  LocalChatReferencesResponse,
  LocalChatSummaryResponse,
} from '@/api/types'

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  references?: LocalChatReferencesResponse | null
  summary?: LocalChatSummaryResponse | null
}

export interface SendMessageOptions {
  content: string
  modelId: string
  datasetId?: string | null
  systemPrompt?: string | null
}

export function useLocalChat() {
  const turns = ref<ChatTurn[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  let abortController: AbortController | null = null

  function buildMessageHistory(): LocalChatMessage[] {
    return turns.value.map((t) => ({
      role: t.role,
      content: t.content,
    }))
  }

  async function sendMessage(options: SendMessageOptions) {
    const { content, modelId, datasetId, systemPrompt } = options

    abortController?.abort()
    abortController = new AbortController()
    const signal = abortController.signal

    turns.value.push({ role: 'user', content })

    loading.value = true
    error.value = null

    try {
      const response = await chatApi.send(
        {
          model_id: modelId,
          dataset_id: datasetId ?? null,
          messages: buildMessageHistory(),
          system_prompt: systemPrompt ?? null,
          max_tokens: 500,
          temperature: 0.7,
        },
        { signal },
      )

      const assistantContent = response.summary?.message.content ?? 'No response from model.'

      turns.value.push({
        role: 'assistant',
        content: assistantContent,
        references: response.references,
        summary: response.summary,
      })
    } catch (e: unknown) {
      if (signal.aborted) return
      error.value = e instanceof Error ? e.message : 'Chat request failed'
    } finally {
      if (!signal.aborted) loading.value = false
    }
  }

  function clearChat() {
    turns.value = []
    error.value = null
  }

  onBeforeUnmount(() => {
    abortController?.abort()
    abortController = null
  })

  return {
    turns,
    loading,
    error,
    sendMessage,
    clearChat,
  }
}
