import { createRouter, createWebHashHistory } from 'vue-router'
import SignInPage from '@/pages/SignInPage.vue'
import MemberPage from '@/pages/MemberPage.vue'
import AdminPage from '@/pages/AdminPage.vue'
import CheckoutPage from '@/pages/CheckoutPage.vue'
import { useSessionStore } from '@/stores/session'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/signin', name: 'signin', component: SignInPage },
    { path: '/', name: 'member', component: MemberPage },
    { path: '/admin', name: 'admin', component: AdminPage },
    // Buy credits — any signed-in user (this is the link admins share).
    { path: '/credits', name: 'credits', component: CheckoutPage },
  ],
})

/**
 * One sign-in for everyone. The station knows which SyftHub account is
 * the admin, so routing is by role: admin → dashboard (first-run setup is a
 * dialog there); everyone else → member view. The credits checkout is open
 * to every signed-in user.
 */
router.beforeEach(async (to) => {
  const session = useSessionStore()
  await session.restore() // no-op after the first navigation

  if (!session.isSignedIn) {
    if (to.name === 'signin') return true
    // Keep the destination so the checkout link survives the sign-in hop.
    return { name: 'signin', query: to.name ? { redirect: to.fullPath } : undefined }
  }

  const home = session.isAdmin ? 'admin' : 'member'

  // Signed-in users never see the sign-in page; role-homes are enforced,
  // but shared pages (credits) are reachable by everyone.
  if (to.name === 'credits') return true
  if (to.name !== home) return { name: home }
  return true
})

export default router
