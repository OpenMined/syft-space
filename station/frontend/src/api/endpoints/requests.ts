import { apiClient } from '@/api/client'
import type {
  ApproveRequestBody,
  PatchRequestBody,
  RequestResponse,
  SubmitRequestBody,
} from '@/api/types'

export const requestsApi = {
  /** Member: own requests. Admin: all requests. */
  list: (): Promise<RequestResponse[]> => apiClient.get('/requests'),

  /** One request — poll this while a create is PROVISIONING. */
  get: (id: string): Promise<RequestResponse> => apiClient.get(`/requests/${id}`),

  /** Submit any request type; payload.type selects the shape. */
  submit: (body: SubmitRequestBody): Promise<RequestResponse> =>
    apiClient.post('/requests', body),

  /** Ask to create a space (member, or admin on a member's behalf). */
  submitCreate: (
    spaceName: string,
    subdomain: string,
    opts: { reason?: string; ownerEmail?: string } = {},
  ): Promise<RequestResponse> =>
    apiClient.post('/requests', {
      payload: { type: 'create_space', space_name: spaceName, subdomain },
      reason: opts.reason,
      owner_email: opts.ownerEmail,
    }),

  /** Ask to delete a space (owner or admin). */
  submitDelete: (spaceId: string, reason = ''): Promise<RequestResponse> =>
    apiClient.post('/requests', {
      payload: { type: 'delete_space' },
      space_id: spaceId,
      reason,
    }),

  /** Move a request to a target status (the one lifecycle verb). */
  patch: (id: string, body: PatchRequestBody): Promise<RequestResponse> =>
    apiClient.patch(`/requests/${id}`, body),

  /** Admin. create_space → provisions; delete_space → tears down. */
  approve: (id: string, body: ApproveRequestBody = {}): Promise<RequestResponse> =>
    requestsApi.patch(id, { status: 'approved', ...body }),

  /** Admin declines a pending request (create or delete). */
  reject: (id: string, reason = ''): Promise<RequestResponse> =>
    requestsApi.patch(id, { status: 'rejected', reason }),

  /** Admin. Re-runs provisioning for a FAILED create (approve again). */
  retry: (id: string): Promise<RequestResponse> =>
    requestsApi.patch(id, { status: 'approved' }),

  /** Owner (or admin) cancels their own PENDING request. */
  withdraw: (id: string): Promise<RequestResponse> =>
    requestsApi.patch(id, { status: 'withdrawn' }),
}
