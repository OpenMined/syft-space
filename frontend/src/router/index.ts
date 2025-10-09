import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import EndpointsPage from '../pages/EndpointsPage.vue'
import DatasetsPage from '../pages/DatasetsPage.vue'
import ModelsPage from '../pages/ModelsPage.vue'
import InboxPage from '../pages/InboxPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import CreateEndpointPage from '../pages/CreateEndpointPage.vue'
import EndpointDetailPage from '../pages/EndpointDetailPage.vue'
import DatasetDetailPage from '../pages/DatasetDetailPage.vue'
import ModelDetailPage from '../pages/ModelDetailPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/home'
    },
    {
      path: '/home',
      name: 'home',
      component: HomePage
    },
    {
      path: '/endpoints',
      name: 'endpoints',
      component: EndpointsPage
    },
    {
      path: '/datasets',
      name: 'datasets',
      component: DatasetsPage
    },
    {
      path: '/models',
      name: 'models',
      component: ModelsPage
    },
    {
      path: '/endpoints/:slug',
      name: 'endpoint-detail',
      component: EndpointDetailPage
    },
    {
      path: '/datasets/:slug',
      name: 'dataset-detail',
      component: DatasetDetailPage
    },
    {
      path: '/models/:slug',
      name: 'model-detail',
      component: ModelDetailPage
    },
    {
      path: '/inbox',
      name: 'inbox',
      component: InboxPage
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsPage
    },
    {
      path: '/create',
      name: 'create',
      component: CreateEndpointPage
    },
    {
      path: '/create/data-endpoint',
      name: 'create-data-endpoint',
      component: () => import('../pages/CreateDataEndpointPage.vue')
    },
    {
      path: '/create/model-endpoint',
      name: 'create-model-endpoint',
      component: () => import('../pages/CreateModelEndpointPage.vue')
    }
  ],
})

export default router
