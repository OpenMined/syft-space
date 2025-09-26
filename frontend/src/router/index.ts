import { createRouter, createWebHistory } from 'vue-router'
import MyServicesPage from '../pages/MyServicesPage.vue'
import InboxPage from '../pages/InboxPage.vue'
import UsagePage from '../pages/UsagePage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import CreateServicePage from '../pages/CreateServicePage.vue'
import ServiceDetailPage from '../pages/ServiceDetailPage.vue'

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
      component: MyServicesPage
    },
    {
      path: '/services/:id',
      name: 'service-detail',
      component: ServiceDetailPage
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
      path: '/create',
      name: 'create',
      component: CreateServicePage
    },
    {
      path: '/create/data-service',
      name: 'create-data-service',
      component: () => import('../pages/CreateDataServicePage.vue')
    },
    {
      path: '/create/model-service',
      name: 'create-model-service',
      component: () => import('../pages/CreateModelServicePage.vue')
    }
  ],
})

export default router
