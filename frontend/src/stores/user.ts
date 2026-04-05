import { defineStore } from 'pinia'
import { ref } from 'vue'
import { marketplacesApi } from '@/api/endpoints/marketplaces'
import { walletsApi } from '@/api/endpoints/wallets'
import { formatPrice } from '@/lib/formatters'
import type { TransactionResponse } from '@/api/types'

export const useUserStore = defineStore('user', () => {
  const name = ref<string | null>(null)
  const username = ref<string | null>(null)
  const email = ref<string | null>(null)
  const balance = ref<number | null>(null)
  const currency = ref('USD')
  const balanceLoading = ref(false)
  const balanceError = ref(false)
  const walletConfigured = ref(false)
  const walletId = ref<string | null>(null)
  const transactions = ref<TransactionResponse[]>([])
  const marketplaceLoading = ref(false)
  const marketplaceUrl = ref<string | null>(null)
  const authToken = ref('')

  const fetchMarketplaceInfo = async () => {
    marketplaceLoading.value = true
    try {
      const marketplaces = await marketplacesApi.list()
      if (marketplaces.length > 0) {
        const lastMarketplace = marketplaces[marketplaces.length - 1]!
        name.value = lastMarketplace.name
        username.value = lastMarketplace.username
        email.value = lastMarketplace.email
        marketplaceUrl.value = lastMarketplace.url
      }
    } catch (error) {
      console.error('Failed to fetch marketplace info:', error)
    } finally {
      marketplaceLoading.value = false
    }
  }

  const fetchWalletInfo = async () => {
    try {
      const wallets = await walletsApi.list()
      const mppWallet = wallets.find((w) => w.wallet_type === 'mpp')
      walletId.value = mppWallet?.id ?? null
      walletConfigured.value = !!mppWallet
    } catch (error) {
      console.error('Failed to fetch wallet info:', error)
      walletId.value = null
      walletConfigured.value = false
    }
  }

  const fetchBalance = async (silent = false) => {
    if (!walletId.value) {
      if (!silent) {
        balance.value = null
        walletConfigured.value = false
      }
      return
    }

    if (!silent) {
      balanceLoading.value = true
      balanceError.value = false
    }
    try {
      const response = await walletsApi.getMppBalance(walletId.value)
      balance.value = response.balance
      currency.value = response.currency
      transactions.value = response.recent_transactions
      walletConfigured.value = response.wallet_configured
      if (silent) {
        balanceError.value = false
      }
    } catch (error) {
      console.error('Failed to fetch balance:', error)
      if (!silent) {
        balance.value = null
        balanceError.value = true
        transactions.value = []
      }
    } finally {
      if (!silent) {
        balanceLoading.value = false
      }
    }
  }

  const formattedBalance = () => {
    if (balance.value === null) return '--'
    return `$${formatPrice(balance.value)}`
  }

  /**
   * Get the marketplace URL for an endpoint
   * @param endpointSlug - The endpoint slug/name
   * @returns The full URL to view the endpoint on the marketplace, or null if not available
   */
  const getEndpointUrlInMarketplace = (endpointSlug: string): string | null => {
    if (marketplaceUrl.value && username.value && endpointSlug) {
      const baseUrl = marketplaceUrl.value.replace(/\/+$/, '')
      return `${baseUrl}/${username.value}/${endpointSlug}`
    }
    return null
  }

  return {
    name,
    username,
    email,
    balance,
    currency,
    walletConfigured,
    walletId,
    balanceLoading,
    balanceError,
    transactions,
    marketplaceLoading,
    marketplaceUrl,
    authToken,
    fetchMarketplaceInfo,
    fetchWalletInfo,
    fetchBalance,
    formattedBalance,
    getEndpointUrlInMarketplace,
  }
})
