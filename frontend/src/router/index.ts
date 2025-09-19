import { createRouter, createWebHistory } from 'vue-router'
import ServicesPage from '../pages/ServicesPage.vue'
import InboxPage from '../pages/InboxPage.vue'
import UsagePage from '../pages/UsagePage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import CreateServicePage from '../pages/CreateServicePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/services'
    },
    {
      path: '/services',
      name: 'services',
      component: ServicesPage
    },
    {
      path: '/inbox',
      name: 'inbox',
      component: InboxPage
    },
    {
      path: '/usage',
      name: 'usage',
      component: UsagePage
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsPage
    },
    {
      path: '/create-service',
      name: 'create-service',
      component: CreateServicePage
    }
  ],
})

export default router
