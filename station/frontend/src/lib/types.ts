export type RequestStatus =
  | 'pending'
  | 'provisioning'
  | 'active'
  | 'rejected'
  | 'failed'
  | 'deleted'
  | 'withdrawn'

export type SpaceHealth = 'healthy' | 'unhealthy' | 'restarting' | 'paused' | 'starting'

export interface SpaceRequest {
  id: string
  spaceName: string
  subdomain: string
  requesterEmail: string
  requesterName?: string
  purpose: string
  createdAt: string
  status: RequestStatus
  rejectReason?: string
  failureError?: string
  spaceId?: string
  /** Set when the admin created the space directly (no member request). */
  origin?: 'admin'
}

export interface Space {
  id: string
  name: string
  subdomain: string
  url: string
  ownerEmail: string
  health: SpaceHealth
  createdAt: string
  /** Space URL with the admin key as authToken — opens the space signed in (owner/admin only). */
  adminUrl?: string
  /** Image tag this space's deployment currently runs. */
  version: string
}

// ---- Shared wallet & earnings (server-backed via /credits) ----

/** Gateway providers only — MPP is explicitly outside the shared-wallet flow. */
export type WalletProvider = 'xendit' | 'stripe'

/** The station's shared gateway wallet (credentials never leave the server). */
export interface SharedWallet {
  provider: WalletProvider
  currency: string
  /** Whether the wallet has a SyftHub identity (API token) to verify buyers with. */
  hubConnected: boolean
}

/** A settled credits purchase (the admin feed and the buyer's history). */
export interface TopUp {
  id: string
  userEmail: string
  bundleName: string
  amount: number
  currency: string
  paidAt: string
}

/** A manual payout recorded by the admin against a space's earned total. */
export interface Payout {
  id: string
  spaceId: string
  amount: number
  paidAt: string
  note?: string
}

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount)
}

export interface ApprovalConfig {
  spaceName: string
  subdomain: string
  /** false → provision without the station wallet (picker in the dialog). */
  attachWallet?: boolean
}

/**
 * What every provisioned space gets — fixed by the station, not chosen per
 * space. The store appends a wallet line when a shared wallet is configured
 * (the shared wallet is optional).
 */
export const SPACE_INCLUDES = [
  'Private, searchable index of your documents',
  'Automatic document processing (PDFs and more)',
  'Your own private storage',
] as const

/** DNS-1123 label: lowercase alphanumeric + hyphens, no leading/trailing hyphen, ≤63 chars. */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, 63)
    .replace(/^-+|-+$/g, '')
}
