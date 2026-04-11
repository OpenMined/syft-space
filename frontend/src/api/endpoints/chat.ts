import { apiClient } from '../client'
import type { LocalChatRequest, LocalChatResponse } from '../types'

export const chatApi = {
  send: async (
    request: LocalChatRequest,
    options?: { signal?: AbortSignal },
  ): Promise<LocalChatResponse> => {
    const response = await apiClient.post<LocalChatResponse>('/chat/', request, {
      signal: options?.signal,
    })
    return response.data
  },
}
