import { ref, onBeforeUnmount } from 'vue'
import { endpointsApi } from '@/api/endpoints/endpoints'
import type { ChatSummaryResponse, ChatReferencesResponse } from '@/api/types'

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  references?: ChatReferencesResponse | null
  summary?: ChatSummaryResponse | null
}

export interface SendMessageOptions {
  content: string
  endpointSlug: string
}

export function useEndpointChat() {
  const turns = ref<ChatTurn[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  let abortController: AbortController | null = null

  function buildHistory() {
    return turns.value.map((t) => ({ role: t.role, content: t.content }))
  }

  async function sendMessage(options: SendMessageOptions) {
    const { content, endpointSlug } = options

    abortController?.abort()
    abortController = new AbortController()
    const signal = abortController.signal

    turns.value.push({ role: 'user', content })

    loading.value = true
    error.value = null

    const history = buildHistory()

    try {
      const response = await endpointsApi.query(
        endpointSlug,
        {
          messages: history,
          max_tokens: 1000,
          temperature: 0.7,
        },
        { signal },
      )

      turns.value.push({
        role: 'assistant',
        content: response.summary?.message.content ?? '(no response)',
        references: response.references,
        summary: response.summary,
      })
    } catch (e: unknown) {
      if (signal.aborted) return
      error.value = e instanceof Error ? e.message : 'Request failed'
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

  return { turns, loading, error, sendMessage, clearChat }
}
