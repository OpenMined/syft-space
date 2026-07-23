import { apiClient } from '@/api/client'
import type {
  CheckoutResponse,
  EarningsResponse,
  MemberEarningsResponse,
  MyCreditsResponse,
  OutstandingBalancesResponse,
  PayoutBody,
  PayoutRecordedResponse,
  WalletSetupBody,
  WalletSetupResponse,
  WalletStatusResponse,
} from '@/api/types'

export const creditsApi = {
  /** Any signed-in user: is a wallet configured, currency + bundle catalog. */
  wallet: (): Promise<WalletStatusResponse> => apiClient.get('/credits/wallet'),
  /** Start a hosted checkout; redirect the buyer to checkout_url. */
  checkout: (bundleName: string): Promise<CheckoutResponse> =>
    apiClient.post('/credits/checkout', { bundle_name: bundleName }),
  /** The signed-in user's balance, purchases, and spend history. */
  me: (): Promise<MyCreditsResponse> => apiClient.get('/credits/me'),
  /** What the member's own spaces earned and are still owed. */
  myEarnings: (): Promise<MemberEarningsResponse> => apiClient.get('/credits/earnings/mine'),
  /** Admin: wallet state, never credentials. */
  adminWallet: (): Promise<WalletStatusResponse> => apiClient.get('/credits/admin/wallet'),
  /** Admin: create or replace the station wallet; attaches unbound spaces. */
  setupWallet: (body: WalletSetupBody): Promise<WalletSetupResponse> =>
    apiClient.put('/credits/admin/wallet', body),
  /** Admin: the ledger-derived money dashboard. */
  earnings: (): Promise<EarningsResponse> => apiClient.get('/credits/admin/earnings'),
  /** Admin: unspent user credit — the station's liability. */
  balances: (): Promise<OutstandingBalancesResponse> => apiClient.get('/credits/admin/balances'),
  /** Admin: record a payout made out-of-band (capped at the space's payable). */
  recordPayout: (body: PayoutBody): Promise<PayoutRecordedResponse> =>
    apiClient.post('/credits/admin/payouts', body),
}
