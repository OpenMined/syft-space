import { apiClient } from '../client'
import type { InvoiceResponse, BundleUsageResponse } from '../types'

export const paymentsApi = {
  getInvoicesByEndpoint: async (endpointSlug: string): Promise<InvoiceResponse[]> => {
    const response = await apiClient.get<InvoiceResponse[]>(
      `/payments/invoices/endpoint/${endpointSlug}`,
    )
    return response.data
  },

  getBundleUsages: async (endpointSlug: string): Promise<BundleUsageResponse[]> => {
    const response = await apiClient.get<BundleUsageResponse[]>('/payments/bundles', {
      params: { endpoint_slug: endpointSlug },
    })
    return response.data
  },
}
