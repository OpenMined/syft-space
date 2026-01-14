import { apiClient } from '../client'
import type {
  RegisterMarketplaceRequest,
  ConnectMarketplaceRequest,
  MarketplaceResponse,
  MarketplaceListItem,
  BalanceResponse,
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

  // Get account balance
  getBalance: async (): Promise<BalanceResponse> => {
    const response = await apiClient.get('/marketplaces/balance')
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
}
