import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const email = ref('user@openmined.org')
  const balance = ref('$87.20')
  const walletManagerUrl = ref('https://payments.openmined.org')
  const authToken = ref('')

  const updateEmail = (newEmail: string) => {
    email.value = newEmail
  }

  const updateBalance = (newBalance: string) => {
    balance.value = newBalance
  }

  const updateWalletManagerUrl = (newUrl: string) => {
    walletManagerUrl.value = newUrl
  }

  const updateAuthToken = (newToken: string) => {
    authToken.value = newToken
  }

  return {
    email,
    balance,
    walletManagerUrl,
    authToken,
    updateEmail,
    updateBalance,
    updateWalletManagerUrl,
    updateAuthToken
  }
})