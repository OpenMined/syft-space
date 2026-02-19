import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api/client'

export const useServerAvailabilityStore = defineStore('serverAvailability', () => {
  const isReady = ref(false)
  const isSlow = ref(false)

  let pollInterval: ReturnType<typeof setInterval> | null = null
  let slowTimeout: ReturnType<typeof setTimeout> | null = null
  let readyResolvers: Array<() => void> = []

  function cleanup() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
    if (slowTimeout) {
      clearTimeout(slowTimeout)
      slowTimeout = null
    }
  }

  function markReady() {
    isReady.value = true
    cleanup()
    for (const resolve of readyResolvers) {
      resolve()
    }
    readyResolvers = []
  }

  async function checkHealth(): Promise<boolean> {
    try {
      const response = await apiClient.get('/health')
      return response.data?.status === 'healthy'
    } catch {
      return false
    }
  }

  async function startPolling() {
    if (isReady.value) return

    const healthy = await checkHealth()
    if (healthy) {
      markReady()
      return
    }

    slowTimeout = setTimeout(() => {
      isSlow.value = true
    }, 8000)

    pollInterval = setInterval(async () => {
      const healthy = await checkHealth()
      if (healthy) {
        markReady()
      }
    }, 1000)
  }

  function waitUntilReady(): Promise<void> {
    if (isReady.value) return Promise.resolve()
    return new Promise((resolve) => {
      readyResolvers.push(resolve)
    })
  }

  return {
    isReady,
    isSlow,
    startPolling,
    waitUntilReady,
  }
})
