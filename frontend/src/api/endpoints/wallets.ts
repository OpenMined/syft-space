import { apiClient } from '../client'
import type { CreateWalletRequest, WalletResponse, WalletListItem } from '../types'

export const walletsApi = {
  list: async (): Promise<WalletListItem[]> => {
    const response = await apiClient.get<WalletListItem[]>('/wallets/')
    return response.data
  },

  create: async (request: CreateWalletRequest): Promise<WalletResponse> => {
    const response = await apiClient.post<WalletResponse>('/wallets/', request)
    return response.data
  },

  get: async (id: string): Promise<WalletResponse> => {
    const response = await apiClient.get<WalletResponse>(`/wallets/${id}`)
    return response.data
  },

  delete: async (id: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/wallets/${id}`)
    return response.data
  },
}
