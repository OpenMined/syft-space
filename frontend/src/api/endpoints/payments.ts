import { apiClient } from '../client'

export interface InvoiceResponse {
  id: string
  endpoint_id: string
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

export interface BundleUsageResponse {
  endpoint_slug: string
  user_email: string
  remaining_balance: number
  total_deposited: number
}

export const paymentsApi = {
  getInvoicesByEndpoint: async (endpointSlug: string): Promise<InvoiceResponse[]> => {
    const response = await apiClient.get(`/payments/gateway/invoices/endpoint/${endpointSlug}`)
    return response.data
  },

  getBundleUsages: async (endpointSlug: string): Promise<BundleUsageResponse[]> => {
    const response = await apiClient.get('/payments/gateway/bundles', {
      params: { endpoint_slug: endpointSlug },
    })
    return response.data
  },
}
