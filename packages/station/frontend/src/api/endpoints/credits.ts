import { apiClient } from '@/api/client'
import type {
  EarningsResponse,
  MemberEarningsResponse,
  OutstandingBalancesResponse,
  PayoutBody,
  PayoutRecordedResponse,
  WalletSetupBody,
  WalletSetupResponse,
  WalletStatusResponse,
} from '@/api/types'

export const creditsApi = {
  /** Any signed-in user: whether a wallet is configured, plus its currency. */
  wallet: (): Promise<WalletStatusResponse> => apiClient.get('/credits/wallet'),
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
