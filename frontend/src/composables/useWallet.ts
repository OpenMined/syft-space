import { ref, computed } from 'vue'
import { walletsApi } from '@/api/endpoints/wallets'
import type { WalletListItem } from '@/api/types'

export interface WalletState {
  id: string
  walletType: string
  webhookUrl: string
  isActive: boolean
}

const wallet = ref<WalletState | null>(null)
const isLoading = ref(false)

export function useWallet() {
  const isConfigured = computed(() => wallet.value !== null)

  const fetchWallet = async () => {
    isLoading.value = true
    try {
      const wallets = await walletsApi.list()
      const xenditWallet = wallets.find((w: WalletListItem) => w.wallet_type === 'xendit')
      if (xenditWallet) {
        wallet.value = {
          id: xenditWallet.id,
          walletType: xenditWallet.wallet_type,
          webhookUrl: xenditWallet.webhook_url || '',
          isActive: xenditWallet.is_active,
        }
      } else {
        wallet.value = null
      }
    } catch {
      wallet.value = null
    } finally {
      isLoading.value = false
    }
  }

  const configure = async (apiKey: string, callbackToken: string): Promise<WalletState> => {
    const response = await walletsApi.create({
      wallet_type: 'xendit',
      api_key: apiKey,
      callback_token: callbackToken,
    })
    const state: WalletState = {
      id: response.id,
      walletType: response.wallet_type,
      webhookUrl: response.webhook_url || '',
      isActive: response.is_active,
    }
    wallet.value = state
    return state
  }

  const remove = async () => {
    if (wallet.value?.id) {
      await walletsApi.delete(wallet.value.id)
    }
    wallet.value = null
  }

  return {
    wallet,
    isConfigured,
    isLoading,
    fetchWallet,
    configure,
    remove,
  }
}
