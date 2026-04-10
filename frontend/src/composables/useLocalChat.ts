import { ref } from 'vue'
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

export function useLocalChat() {
  const turns = ref<ChatTurn[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const modelId = ref<string | null>(null)
  const datasetId = ref<string | null>(null)

  function buildMessageHistory(): LocalChatMessage[] {
    return turns.value.map((t) => ({
      role: t.role,
      content: t.content,
    }))
  }

  async function sendMessage(content: string) {
    if (!modelId.value) return

    const userTurn: ChatTurn = { role: 'user', content }
    turns.value.push(userTurn)

    loading.value = true
    error.value = null

    try {
      const response = await chatApi.send({
        model_id: modelId.value,
        dataset_id: datasetId.value,
        messages: buildMessageHistory(),
        max_tokens: 500,
        temperature: 0.7,
      })

      const assistantContent = response.summary?.message.content ?? 'No response from model.'

      turns.value.push({
        role: 'assistant',
        content: assistantContent,
        references: response.references,
        summary: response.summary,
      })
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Chat request failed'
      error.value = message
      turns.value.pop()
    } finally {
      loading.value = false
    }
  }

  function clearChat() {
    turns.value = []
    error.value = null
  }

  return {
    turns,
    loading,
    error,
    modelId,
    datasetId,
    sendMessage,
    clearChat,
  }
}
