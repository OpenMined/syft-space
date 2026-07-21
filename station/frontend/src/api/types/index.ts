/**
 * Wire types for the station API — snake_case fields mirroring the backend
 * Pydantic schemas (the OpenAPI reference lives at /docs on the backend).
 */

export type Role = 'admin' | 'member'

export interface MeResponse {
  email: string
  username: string
  name: string
  role: Role
}

export interface LoginBody {
  email: string
  password: string
}

export interface SetupResponse {
  domain: string
  supported_version: string
  onboarded: boolean
}

export interface UpdateSetupBody {
  domain?: string
  supported_version?: string
}

export type ApiRequestStatus =
  | 'pending'
  | 'provisioning'
  | 'active'
  | 'rejected'
  | 'failed'
  | 'deleted'
  | 'withdrawn'

export type RequestOrigin = 'member' | 'admin'

export interface RequestResponse {
  id: string
  space_name: string
  subdomain: string
  owner_email: string
  reason: string
  origin: RequestOrigin
  status: ApiRequestStatus
  reject_reason: string | null
  space_id: string | null
  created_at: string
  updated_at: string
}

export interface SubmitRequestBody {
  space_name: string
  subdomain: string
  reason?: string
}

/** Admin review-and-confirm: name/subdomain editable for conflicts. */
export interface ApproveRequestBody {
  space_name?: string
  subdomain?: string
}

export interface RejectRequestBody {
  reason?: string
}

export interface SpaceResponse {
  id: string
  request_id: string | null
  name: string
  subdomain: string
  owner_email: string
  url: string
  version: string
  created_at: string
}

/** Live runtime status of a space, read from Kubernetes (never stored). */
export type SpaceRuntimeStatus = 'running' | 'paused' | 'unavailable' | 'not_found'

export interface SpaceStatusResponse {
  status: SpaceRuntimeStatus
}

export interface TokenStatusResponse {
  revealed: boolean
  created_at: string
}

/** One-time reveal of the space admin API key. */
export interface TokenRevealResponse {
  token: string
}

export interface ImageTagResponse {
  tag: string
  created: string
  revision: string | null
  is_latest: boolean
}
