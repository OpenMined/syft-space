import { apiClient } from '@/api/client'
import type {
  ApproveRequestBody,
  RejectRequestBody,
  RequestResponse,
  SubmitRequestBody,
} from '@/api/types'

export const requestsApi = {
  /** Member: own requests. Admin: all requests. */
  list: (): Promise<RequestResponse[]> => apiClient.get('/requests'),

  /** One request — poll this while it's PROVISIONING. */
  get: (id: string): Promise<RequestResponse> => apiClient.get(`/requests/${id}`),

  submit: (body: SubmitRequestBody): Promise<RequestResponse> => apiClient.post('/requests', body),

  /** Admin. Starts provisioning in the background; 409 on subdomain conflict. */
  approve: (id: string, body: ApproveRequestBody = {}): Promise<RequestResponse> =>
    apiClient.post(`/requests/${id}/approve`, body),

  /** Admin. */
  reject: (id: string, body: RejectRequestBody = {}): Promise<RequestResponse> =>
    apiClient.post(`/requests/${id}/reject`, body),

  /** Admin. Re-runs provisioning for a FAILED request. */
  retry: (id: string): Promise<RequestResponse> => apiClient.post(`/requests/${id}/retry`),

  /** Owner or admin. Tears the space down completely, data included. */
  deleteSpace: (id: string): Promise<RequestResponse> => apiClient.post(`/requests/${id}/delete`),

  /** Member withdraws their own PENDING request. */
  withdraw: (id: string): Promise<RequestResponse> => apiClient.post(`/requests/${id}/withdraw`),
}
