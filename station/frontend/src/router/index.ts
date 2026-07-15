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
    { path: '/admin', name: 'admin', component: AdminPage },
  ],
})

/**
 * One sign-in for everyone. The station knows which SyftHub account is
 * the admin, so routing is by role: admin → dashboard (first-run setup is a
 * dialog there); everyone else → member view.
 */
router.beforeEach((to) => {
  const session = useSessionStore()

  if (!session.isSignedIn) {
    return to.name === 'signin' ? true : { name: 'signin' }
  }

  const home = session.isAdmin ? 'admin' : 'member'

  // Signed-in users never see the sign-in page; everyone lands on their home
  if (to.name !== home) return { name: home }
  return true
})

export default router
