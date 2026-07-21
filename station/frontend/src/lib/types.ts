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
  url: string
  ownerEmail: string
  health: SpaceHealth
  createdAt: string
  /** Whether the one-time API key reveal has been used (from the token endpoint). */
  apiKeyClaimed: boolean
  /** Image tag this space's deployment currently runs. */
  version: string
  /** Whether the current shared-wallet config has been seeded (applies on pod restart). */
  walletSeeded: boolean
}

// ---- Shared wallet & earnings ----

/** Gateway providers only — MPP is explicitly outside the shared-wallet flow. */
export type WalletProvider = 'xendit' | 'stripe'

/** The station's shared gateway wallet, seeded into every space. */
export interface SharedWallet {
  provider: WalletProvider
  currency: string
  /** Masked credential for display, e.g. "xnd_prod_••••3kf9" */
  maskedKey: string
  createdAt: string
}

/**
 * Credits a user bought at the station's checkout. The gateway notifies
 * the station directly — spaces are never involved in payments.
 */
export interface TopUp {
  id: string
  userEmail: string
  amount: number
  currency: string
  paidAt: string
}

/**
 * A daily per-user spend aggregate from the station's credit ledger:
 * per-query price × queries, attributed to the space whose token authorized
 * the debits. Source of truth for what each space earned.
 */
export interface CreditDebit {
  id: string
  spaceSlug: string
  spaceName: string
  ownerEmail: string
  userEmail: string
  amount: number
  queries: number
  day: string
}

/** A manual payout recorded by the admin against a space's earned total. */
export interface Payout {
  id: string
  spaceSlug: string
  amount: number
  currency: string
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
