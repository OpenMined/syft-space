import { apiClient } from '../client'
import type { LocalChatRequest, LocalChatResponse } from '../types'

export const chatApi = {
  send: async (request: LocalChatRequest): Promise<LocalChatResponse> => {
    const response = await apiClient.post<LocalChatResponse>('/chat/', request)
    return response.data
  },
}
