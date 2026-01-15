import { defineStore } from 'pinia'
import { ref } from 'vue'
import { marketplacesApi } from '@/api/endpoints/marketplaces'
import { formatPrice } from '@/lib/formatters'

export const useUserStore = defineStore('user', () => {
  const name = ref<string | null>(null)
  const username = ref<string | null>(null)
  const email = ref<string | null>(null)
  const balance = ref<number | null>(null)
  const currency = ref('USD')
  const balanceLoading = ref(false)
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

  const fetchBalance = async () => {
    balanceLoading.value = true
    try {
      const response = await marketplacesApi.getBalance()
      balance.value = response.balance
      currency.value = response.currency
    } catch (error) {
      console.error('Failed to fetch balance:', error)
      balance.value = null
    } finally {
      balanceLoading.value = false
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
    balanceLoading,
    marketplaceLoading,
    marketplaceUrl,
    authToken,
    fetchMarketplaceInfo,
    fetchBalance,
    formattedBalance,
    getEndpointUrlInMarketplace,
  }
})
