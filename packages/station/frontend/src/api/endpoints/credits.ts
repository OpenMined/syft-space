import { apiClient } from '@/api/client'
import type {
  EarningsResponse,
  MemberEarningsResponse,
  OutstandingBalanceResponse,
  Page,
  PayoutInfoResponse,
  SpaceEarningsResponse,
  TopUpResponse,
  PayoutBody,
  PayoutRecordedResponse,
  WalletSetupBody,
  WalletStatusResponse,
} from '@/api/types'

/** Matches the backend's default — a page fits without inner scrolling. */
const PAGE_SIZE = 10
/** The chart window; the server aggregates to one row per day. */
export const CHART_DAYS = 14

export const creditsApi = {
  /** Any signed-in user: whether a wallet is configured, plus its currency. */
  wallet: (): Promise<WalletStatusResponse> => apiClient.get('/credits/wallet'),
  /** What the member's own spaces earned and are still owed. */
  myEarnings: (): Promise<MemberEarningsResponse> => apiClient.get('/credits/earnings/mine'),
  /** Admin: wallet state, never credentials. */
  adminWallet: (): Promise<WalletStatusResponse> => apiClient.get('/credits/admin/wallet'),
  /** Admin: create or replace the station wallet; attaches unbound spaces. */
  setupWallet: (body: WalletSetupBody): Promise<WalletStatusResponse> =>
    apiClient.put('/credits/admin/wallet', body),
  /** Admin: totals, per-space earnings, and the chart series for `days`. */
  earnings: (days = CHART_DAYS): Promise<EarningsResponse> =>
    apiClient.get(`/credits/admin/earnings?days=${days}`),
  /** Admin: unspent user credit — one page of the station's liability. */
  balances: (limit = PAGE_SIZE, offset = 0): Promise<Page<OutstandingBalanceResponse>> =>
    apiClient.get(`/credits/admin/balances?limit=${limit}&offset=${offset}`),

  /** What each space earned and is owed — sorted by payable, one page. */
  spaceEarnings: (limit = PAGE_SIZE, offset = 0): Promise<Page<SpaceEarningsResponse>> =>
    apiClient.get(`/credits/admin/earnings/spaces?limit=${limit}&offset=${offset}`),

  /** One space's money row — the delete dialog's unpaid-payable warning. */
  spaceEarning: (spaceId: string): Promise<SpaceEarningsResponse> =>
    apiClient.get(`/credits/admin/earnings/spaces/${spaceId}`),

  /** Recorded payouts, newest first. */
  payouts: (limit = PAGE_SIZE, offset = 0): Promise<Page<PayoutInfoResponse>> =>
    apiClient.get(`/credits/admin/payouts?limit=${limit}&offset=${offset}`),

  /** Settled credit purchases, newest first. */
  topUps: (limit = PAGE_SIZE, offset = 0): Promise<Page<TopUpResponse>> =>
    apiClient.get(`/credits/admin/top-ups?limit=${limit}&offset=${offset}`),
  /** Admin: record a payout made out-of-band (capped at the space's payable). */
  recordPayout: (body: PayoutBody): Promise<PayoutRecordedResponse> =>
    apiClient.post('/credits/admin/payouts', body),
}
