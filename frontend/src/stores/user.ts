import { defineStore } from 'pinia'
import { ref } from 'vue'
import { marketplacesApi } from '@/api/endpoints/marketplaces'
import { formatPrice } from '@/lib/formatters'

export const useUserStore = defineStore('user', () => {
  const email = ref<string | null>(null)
  const balance = ref<number | null>(null)
  const currency = ref('USD')
  const balanceLoading = ref(false)
  const marketplaceUrl = ref<string | null>(null)
  const authToken = ref('')

  const fetchMarketplaceInfo = async () => {
    try {
      const marketplaces = await marketplacesApi.list()
      if (marketplaces.length > 0) {
        const lastMarketplace = marketplaces[marketplaces.length - 1]!
        email.value = lastMarketplace.email
        marketplaceUrl.value = lastMarketplace.url
      }
    } catch (error) {
      console.error('Failed to fetch marketplace info:', error)
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

  return {
    email,
    balance,
    currency,
    balanceLoading,
    marketplaceUrl,
    authToken,
    fetchMarketplaceInfo,
    fetchBalance,
    formattedBalance,
  }
})
