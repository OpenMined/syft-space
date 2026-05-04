import { apiClient } from '../client'
import type { LedgerEntryPage, UserBalanceResponse } from '../types'

export interface InvoiceResponse {
  id: string
  wallet_id: string | null
  endpoint_id: string | null
  user_email: string
  provider: string
  external_id: string
  checkout_url: string
  bundle_name: string
  amount: number
  currency: string
  status: string
  paid_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateInvoiceRequest {
  bundle_name: string
  endpoint_slug?: string
}

export const paymentsApi = {
  // ── Public (satellite-token authenticated) ──

  createInvoice: async (
    walletId: string,
    request: CreateInvoiceRequest,
  ): Promise<InvoiceResponse> => {
    const response = await apiClient.post(`/payments/gateway/wallets/${walletId}/invoices`, request)
    return response.data
  },

  getBalance: async (walletId: string): Promise<UserBalanceResponse> => {
    const response = await apiClient.get(`/payments/gateway/wallets/${walletId}/balance`)
    return response.data
  },

  listMyTransactions: async (
    walletId: string,
    params?: { cursor?: string; limit?: number },
  ): Promise<LedgerEntryPage> => {
    const response = await apiClient.get(`/payments/gateway/wallets/${walletId}/transactions/me`, {
      params,
    })
    return response.data
  },

  // ── Admin (tenant-authenticated) ──

  getInvoiceById: async (invoiceId: string): Promise<InvoiceResponse> => {
    const response = await apiClient.get(`/payments/gateway/invoices/${invoiceId}`)
    return response.data
  },

  getInvoicesByWallet: async (walletId: string): Promise<InvoiceResponse[]> => {
    const response = await apiClient.get(`/payments/gateway/wallets/${walletId}/invoices`)
    return response.data
  },

  listInvoices: async (params?: { status?: string }): Promise<InvoiceResponse[]> => {
    const response = await apiClient.get('/payments/gateway/invoices', { params })
    return response.data
  },

  listWalletTransactions: async (
    walletId: string,
    params?: { cursor?: string; limit?: number },
  ): Promise<LedgerEntryPage> => {
    const response = await apiClient.get(`/payments/gateway/wallets/${walletId}/transactions`, {
      params,
    })
    return response.data
  },

  listEndpointTransactions: async (
    endpointId: string,
    params?: { cursor?: string; limit?: number },
  ): Promise<LedgerEntryPage> => {
    const response = await apiClient.get(`/payments/gateway/endpoints/${endpointId}/transactions`, {
      params,
    })
    return response.data
  },
}
