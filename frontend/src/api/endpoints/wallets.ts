import { apiClient } from '../client'
import type {
  WalletResponse,
  WalletListItem,
  MppBalanceResponse,
  TransactionResponse,
} from '../types'

export const walletsApi = {
  // --- Generic (all wallet types) ---

  list: async (): Promise<WalletListItem[]> => {
    const response = await apiClient.get('/wallets/')
    return response.data
  },

  get: async (id: string): Promise<WalletResponse> => {
    const response = await apiClient.get(`/wallets/${id}`)
    return response.data
  },

  delete: async (id: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/wallets/${id}`)
    return response.data
  },

  // --- MPP ---

  createMpp: async (name?: string): Promise<WalletResponse> => {
    const response = await apiClient.post('/wallets/mpp/', { name })
    return response.data
  },

  importMpp: async (privateKey: string, name?: string): Promise<WalletResponse> => {
    const response = await apiClient.post('/wallets/mpp/import', {
      private_key: privateKey,
      name,
    })
    return response.data
  },

  updateMppAddress: async (walletId: string, walletAddress: string): Promise<WalletResponse> => {
    const response = await apiClient.put(`/wallets/mpp/${walletId}/address`, {
      wallet_address: walletAddress,
    })
    return response.data
  },

  getMppBalance: async (walletId: string): Promise<MppBalanceResponse> => {
    const response = await apiClient.get(`/wallets/mpp/${walletId}/balance`)
    return response.data
  },

  getMppTransactions: async (walletId: string): Promise<TransactionResponse[]> => {
    const response = await apiClient.get(`/wallets/mpp/${walletId}/transactions`)
    return response.data
  },

  // --- Gateway ---

  createXendit: async (params: {
    apiKey: string
    callbackToken: string
    currency: string
    country: string
    name?: string
  }): Promise<WalletResponse> => {
    const response = await apiClient.post('/wallets/gateway/xendit', {
      api_key: params.apiKey,
      callback_token: params.callbackToken,
      currency: params.currency,
      country: params.country,
      name: params.name,
    })
    return response.data
  },

  updateXendit: async (
    walletId: string,
    updates: { api_key?: string; callback_token?: string },
  ): Promise<WalletResponse> => {
    const response = await apiClient.put(`/wallets/gateway/xendit/${walletId}`, updates)
    return response.data
  },
}
