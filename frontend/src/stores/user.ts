import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const email = ref('user@openmined.org')
  const balance = ref('$87.20')
  const walletManagerUrl = ref('https://payments.openmined.org')
  const authToken = ref('')

  return {
    email,
    balance,
    walletManagerUrl,
    authToken,
  }
})
