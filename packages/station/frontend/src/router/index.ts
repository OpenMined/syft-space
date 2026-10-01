import { createRouter, createWebHashHistory } from 'vue-router'
import SignInPage from '@/pages/SignInPage.vue'
import MemberPage from '@/pages/MemberPage.vue'
import AdminPage from '@/pages/AdminPage.vue'
import { useSessionStore } from '@/stores/session'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/signin', name: 'signin', component: SignInPage },
    { path: '/', name: 'member', component: MemberPage },
    // The section rides in the URL so it survives a refresh, moves with the
    // back button, and can be linked to. One route, not children: the
    // sections still share AdminPage's state.
    { path: '/admin/:section?/:tab?', name: 'admin', component: AdminPage },
  ],
})

/**
 * One sign-in for everyone. The station knows which SyftHub account is
 * the admin, so routing is by role: admin → dashboard (first-run setup is a
 * dialog there); everyone else → member view. Buyers never touch the station
 * UI — they purchase credits through SyftHub.
 */
router.beforeEach(async (to) => {
  const session = useSessionStore()
  await session.restore() // no-op after the first navigation

  if (!session.isSignedIn) {
    if (to.name === 'signin') return true
    // Keep the destination so it survives the sign-in hop.
    return { name: 'signin', query: to.name ? { redirect: to.fullPath } : undefined }
  }

  const home = session.isAdmin ? 'admin' : 'member'
  if (to.name !== home) return { name: home }
  // Canonical admin URL always names its section, so a copied link and a
  // refresh land in the same place.
  if (home === 'admin' && !to.params.section) {
    return { name: 'admin', params: { section: 'requests' } }
  }
  return true
})

export default router
