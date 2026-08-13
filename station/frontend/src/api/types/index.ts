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

export type RequestType = 'create_space' | 'delete_space'

/** Generic review lifecycle. provisioning/failed apply only to create_space. */
export type ApiRequestStatus =
  | 'pending'
  | 'provisioning'
  | 'approved'
  | 'rejected'
  | 'withdrawn'
  | 'failed'

export type RequestOrigin = 'member' | 'admin'

export interface RequestResponse {
  id: string
  type: RequestType
  status: ApiRequestStatus
  owner_email: string
  space_id: string | null
  space_name: string | null
  subdomain: string | null
  reason: string
  resolution_note: string | null
  payload: Record<string, unknown>
  origin: RequestOrigin
  created_at: string
  updated_at: string
  resolved_at: string | null
}

/** Discriminated on `type`, matching the backend payload union. */
export type CreateSpacePayload = { type: 'create_space'; space_name: string; subdomain: string }
export type DeleteSpacePayload = { type: 'delete_space' }
export type RequestPayload = CreateSpacePayload | DeleteSpacePayload

export interface SubmitRequestBody {
  payload: RequestPayload
  reason?: string
  /** Target space (required for delete_space; ignored by create_space). */
  space_id?: string
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

/** PATCH /requests/{id}: drive the lifecycle by target status. approved/
 *  rejected are admin-only; withdrawn is the owner's. */
export interface PatchRequestBody {
  status: 'approved' | 'rejected' | 'withdrawn'
  reason?: string
  space_name?: string
  subdomain?: string
  attach_wallet?: boolean
  wallet_id?: string
}

export interface SpaceResponse {
  id: string
  request_id: string | null
  name: string
  subdomain: string
  owner_email: string
  url: string
  version: string
  /** A Secret patch is waiting for a restart the station couldn't do itself. */
  restart_required: boolean
  created_at: string
}

/** One space's outcome in an update sweep. */
export interface SpaceUpdateResult {
  space_id: string
  name: string
  outcome: 'updated' | 'skipped' | 'failed'
  detail: string
}

export interface UpdateAllResponse {
  supported_version: string
  results: SpaceUpdateResult[]
}

/** Live runtime status of a space, read from Kubernetes (never stored). */
export type SpaceRuntimeStatus = 'running' | 'paused' | 'unavailable' | 'not_found'

export interface SpaceStatusResponse {
  status: SpaceRuntimeStatus
}

export interface SpaceLogsResponse {
  lines: string[]
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
  /** SyftHub user id the wallet's spaces publish as their owner; null = no hub identity yet. */
  wallet_owner: number | null
}

export interface WalletSetupBody {
  provider: string
  currency: string
  /** { api_key, callback_token } for Xendit; { secret_key, webhook_secret } for Stripe. */
  credentials: Record<string, string>
  /** Existing SyftHub API token (syft_pat_…) to adopt; wins over the password. */
  syfthub_api_token?: string
  /** SyftHub password — used once to mint a fresh API token, then discarded. */
  syfthub_password?: string
}

export interface WalletSetupResponse extends WalletStatusResponse {
  spaces_attached: number
  spaces_failed: number
}

export interface HubTokenMintBody {
  /** Admin's SyftHub password — forwarded to the hub once, never stored. */
  password: string
}

/** A freshly minted SyftHub API token. Held in memory only and submitted
 *  back as syfthub_api_token on wallet save; shown truncated, never persisted. */
export interface HubTokenMintResponse {
  token: string
  username: string
  email: string
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
  name: string
  subdomain: string
  owner_email: string
  /** Space was torn down; money stays payable. */
  deleted: boolean
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
  /** Space was torn down; money stays payable. */
  deleted: boolean
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
