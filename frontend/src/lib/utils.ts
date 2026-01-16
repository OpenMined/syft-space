import type { ClassValue } from 'clsx'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { useUserStore } from '@/stores/user'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Load all globally needed data from various stores.
 * Call this on app mount and after onboarding completes.
 */
export async function loadGlobalData() {
  const userStore = useUserStore()

  await Promise.all([userStore.fetchMarketplaceInfo(), userStore.fetchBalance()])
}
