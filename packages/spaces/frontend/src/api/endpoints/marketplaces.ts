import { apiClient } from '../client'
import {
  MarketplaceErrorCode,
  type RegisterMarketplaceRequest,
  type ConnectMarketplaceRequest,
  type MarketplaceResponse,
  type MarketplaceListItem,
  type VerifyMarketplaceOTPRequest,
  type ResendMarketplaceOTPRequest,
} from '../types'

export type RegisterMarketplaceResult =
  | { kind: 'success'; marketplace: MarketplaceResponse }
  | { kind: 'verification_required'; email: string; url: string; message: string }

export const marketplacesApi = {
  register: async (data: RegisterMarketplaceRequest): Promise<RegisterMarketplaceResult> => {
    const response = await apiClient.post('/marketplaces/register', data)
    if (
      response.status === 202 &&
      response.data?.code === MarketplaceErrorCode.EmailVerificationRequired
    ) {
      return {
        kind: 'verification_required',
        email: response.data.email,
        url: response.data.url,
        message: response.data.message,
      }
    }
    return { kind: 'success', marketplace: response.data as MarketplaceResponse }
  },

  connect: async (data: ConnectMarketplaceRequest): Promise<MarketplaceResponse> => {
    const response = await apiClient.post('/marketplaces/connect', data)
    return response.data
  },

  verifyOtp: async (data: VerifyMarketplaceOTPRequest): Promise<MarketplaceResponse> => {
    const response = await apiClient.post('/marketplaces/verify-otp', data)
    return response.data
  },

  resendOtp: async (data: ResendMarketplaceOTPRequest): Promise<{ message: string }> => {
    const response = await apiClient.post('/marketplaces/resend-otp', data)
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
