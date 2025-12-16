import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import CollectivesPage from '../pages/CollectivesPage.vue'
import CollectiveDetailPage from '../pages/CollectiveDetailPage.vue'
import CreateCollectivePage from '../pages/CreateCollectivePage.vue'
import RequestsPage from '../pages/RequestsPage.vue'
import MembersPage from '../pages/MembersPage.vue'
import CollectiveTermsPage from '../pages/CollectiveTermsPage.vue'
import CollectiveSettingsPage from '../pages/CollectiveSettingsPage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
    },
    {
      path: '/collectives',
      name: 'collectives',
      component: CollectivesPage,
    },
    {
      path: '/collectives/:slug',
      name: 'collective-detail',
      component: CollectiveDetailPage,
    },
    {
      path: '/collectives/:slug/members',
      name: 'collective-members',
      component: MembersPage,
    },
    {
      path: '/collectives/:slug/terms',
      name: 'collective-terms',
      component: CollectiveTermsPage,
    },
    {
      path: '/collectives/:slug/settings',
      name: 'collective-settings',
      component: CollectiveSettingsPage,
    },
    {
      path: '/create',
      name: 'create-collective',
      component: CreateCollectivePage,
    },
    {
      path: '/requests',
      name: 'requests',
      component: RequestsPage,
    },
  ],
})

export default router


