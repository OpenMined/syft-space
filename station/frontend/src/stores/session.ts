import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { HubProfile } from '@/lib/types'
import { ADMIN_EMAIL } from '@/lib/types'

/**
 * Mock SyftHub session.
 *
 * Real flow (v1): station backend proxies email+password to SyftHub
 * /auth/login, fetches /users/me, discards credentials, issues its own
 * session cookie. Here we fabricate the profile from the email.
 */
export const useSessionStore = defineStore('session', () => {
  const profile = ref<HubProfile | null>(null)

  const isSignedIn = computed(() => profile.value !== null)

  /**
   * One sign-in for everyone: the station knows which SyftHub account is
   * the admin (seeded at deploy time) and routes to the right view.
   */
  const isAdmin = computed(() => profile.value?.email === ADMIN_EMAIL)

  async function signIn(email: string, _password: string): Promise<HubProfile> {
    // Simulate the hub round-trip
    await new Promise((r) => setTimeout(r, 600))
    const username = email.split('@')[0] || 'user'
    profile.value = {
      email,
      username,
      fullName: username
        .split(/[._-]/)
        .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
        .join(' '),
      domain: `${username}.syfthub.openmined.org`,
    }
    return profile.value
  }

  function signOut() {
    profile.value = null
  }

  return { profile, isSignedIn, isAdmin, signIn, signOut }
})
