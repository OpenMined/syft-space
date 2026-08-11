import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { ApiError } from '@/api/client'
import { authApi } from '@/api/endpoints/auth'
import type { MeResponse, Role } from '@/api/types'

export interface SessionProfile {
  email: string
  username: string
  fullName: string
  role: Role
}

function toProfile(me: MeResponse): SessionProfile {
  return { email: me.email, username: me.username, fullName: me.name, role: me.role }
}

/**
 * The station session.
 *
 * Sign-in proxies SyftHub credentials to the backend, which verifies them
 * with the hub and answers with an HTTP-only session cookie. The profile
 * (including the role — the backend decides who the admin is) is restored
 * from that cookie on reload via /auth/me.
 */
export const useSessionStore = defineStore('session', () => {
  const profile = ref<SessionProfile | null>(null)

  const isSignedIn = computed(() => profile.value !== null)
  const isAdmin = computed(() => profile.value?.role === 'admin')

  async function signIn(email: string, password: string): Promise<SessionProfile> {
    profile.value = toProfile(await authApi.login({ email, password }))
    return profile.value
  }

  /**
   * Restore the session from the cookie, once per app load (the router
   * guard awaits this before deciding where to send the user). Signed out
   * or unreachable backend both simply mean "no session".
   */
  let restoration: Promise<void> | null = null
  function restore(): Promise<void> {
    restoration ??= (async () => {
      if (profile.value) return
      try {
        profile.value = toProfile(await authApi.me())
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) {
          console.warn('Session restore failed:', error)
        }
      }
    })()
    return restoration
  }

  function signOut() {
    profile.value = null
    // Best-effort cookie clear; the UI state is already signed out.
    authApi.logout().catch(() => {})
  }

  return { profile, isSignedIn, isAdmin, signIn, restore, signOut }
})
