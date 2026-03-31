import { apiClient } from '../client'
import type {
  RegisterMarketplaceRequest,
  ConnectMarketplaceRequest,
  MarketplaceResponse,
  MarketplaceListItem,
  BalanceResponse,
  TransactionResponse,
  WalletResponse,
  CreateWalletResponse,
} from '../types'

export const marketplacesApi = {
  // Register a new marketplace (create new SyftHub account)
  register: async (data: RegisterMarketplaceRequest): Promise<MarketplaceResponse> => {
    const response = await apiClient.post('/marketplaces/register', data)
    return response.data
  },

  // Connect to existing SyftHub account
  connect: async (data: ConnectMarketplaceRequest): Promise<MarketplaceResponse> => {
    const response = await apiClient.post('/marketplaces/connect', data)
    return response.data
  },

  // Check username availability
  checkUsernameAvailability: async (username: string, url?: string): Promise<boolean> => {
    const params = url ? { url } : {}
    const response = await apiClient.get(`/marketplaces/check-username/${username}`, { params })
    return response.data
  },

  // List all marketplaces
  list: async (): Promise<MarketplaceListItem[]> => {
    const response = await apiClient.get('/marketplaces/')
    return response.data
  },

  // Get account balance with recent transactions
  getBalance: async (): Promise<BalanceResponse> => {
    const response = await apiClient.get('/marketplaces/balance')
    return response.data
  },

  // Get all transactions
  getTransactions: async (): Promise<TransactionResponse[]> => {
    const response = await apiClient.get('/marketplaces/transactions')
    return response.data
  },

  // Get specific marketplace details
  get: async (id: string): Promise<MarketplaceResponse> => {
    const response = await apiClient.get(`/marketplaces/${id}`)
    return response.data
  },

  // Delete a marketplace
  delete: async (id: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/marketplaces/${id}`)
    return response.data
  },

  // Wallet management
  getWallet: async (): Promise<WalletResponse> => {
    const response = await apiClient.get('/marketplaces/wallet')
    return response.data
  },

  createWallet: async (): Promise<CreateWalletResponse> => {
    const response = await apiClient.post('/marketplaces/wallet/create')
    return response.data
  },

  importWallet: async (privateKey: string): Promise<CreateWalletResponse> => {
    const response = await apiClient.post('/marketplaces/wallet/import', {
      private_key: privateKey,
    })
    return response.data
  },

  updateWalletAddress: async (walletAddress: string): Promise<WalletResponse> => {
    const response = await apiClient.put('/marketplaces/wallet', { wallet_address: walletAddress })
    return response.data
  },
}
