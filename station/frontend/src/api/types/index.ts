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
  /** The station's own public host, shown at onboarding so the admin confirms
   *  it and hangs spaces off it. Empty in host-run dev (type the domain). */
  station_host: string
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
  /** Admin only: create the space for this member (ignored for members). */
  owner_email?: string
}

/** Admin review-and-confirm: name/subdomain editable for conflicts. */
export interface ApproveRequestBody {
  space_name?: string
  subdomain?: string
  /** false → provision without the station wallet (default true). */
  attach_wallet?: boolean
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

/** The space URL with the admin key attached as authToken. */
export interface AdminUrlResponse {
  url: string
}

export interface ImageTagResponse {
  tag: string
  created: string
  revision: string | null
  is_latest: boolean
}

// ---- Credits ----

/** Wallet state without secrets. The purchasable bundle catalog lives with
 *  the spaces (published on their endpoints), not here — the station only
 *  moves money. */
export interface WalletStatusResponse {
  configured: boolean
  provider: string | null
  currency: string | null
}

export interface WalletSetupBody {
  provider: string
  currency: string
  /** Provider credentials, e.g. { api_key, callback_token } for Xendit. */
  credentials: Record<string, string>
}

export interface WalletSetupResponse extends WalletStatusResponse {
  spaces_attached: number
  spaces_failed: number
}

export interface TopUpResponse {
  invoice_id: string
  user_email: string
  bundle_name: string
  amount: number
  currency: string
  status: string
  created_at: string
  paid_at: string | null
}

export interface EarningsTotalsResponse {
  credits_sold: number
  earned: number
  paid_out: number
  outstanding_balance: number
}

export interface SpaceEarningsResponse {
  space_id: string
  earned: number
  query_count: number
  paid_out: number
  payable: number
}

export interface EndpointEarningsResponse {
  space_id: string
  endpoint: string
  earned: number
  query_count: number
}

export interface DailyEarningsResponse {
  day: string
  space_id: string
  earned: number
  query_count: number
}

export interface PayoutInfoResponse {
  id: string
  space_id: string
  amount: number
  note: string
  created_at: string
}

export interface EarningsResponse {
  currency: string
  totals: EarningsTotalsResponse
  spaces: SpaceEarningsResponse[]
  endpoints: EndpointEarningsResponse[]
  daily: DailyEarningsResponse[]
  recent_top_ups: TopUpResponse[]
  payouts: PayoutInfoResponse[]
}

export interface MemberSpaceEarningsResponse {
  space_id: string
  name: string
  subdomain: string
  earned: number
  query_count: number
  paid_out: number
  payable: number
}

export interface MemberEarningsResponse {
  currency: string
  spaces: MemberSpaceEarningsResponse[]
  total_earned: number
  total_paid_out: number
  total_payable: number
}

export interface OutstandingBalanceResponse {
  user_email: string
  topped_up: number
  spent: number
  balance: number
}

export interface OutstandingBalancesResponse {
  total: number
  balances: OutstandingBalanceResponse[]
}

export interface PayoutBody {
  space_id: string
  amount: number
  note?: string
}

export interface PayoutRecordedResponse {
  id: string
  space_id: string
  amount: number
  note: string
  created_at: string
  payable_after: number
}
