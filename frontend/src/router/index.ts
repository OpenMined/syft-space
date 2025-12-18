import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import EndpointsPage from '../pages/EndpointsPage.vue'
import DatasetsPage from '../pages/DatasetsPage.vue'
import ModelsPage from '../pages/ModelsPage.vue'
import InboxPage from '../pages/InboxPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import AnalyticsPage from '../pages/AnalyticsPage.vue'
import EndpointDetailPage from '../pages/EndpointDetailPage.vue'
import DatasetDetailPage from '../pages/DatasetDetailPage.vue'
import ModelDetailPage from '../pages/ModelDetailPage.vue'
import CreateDataEndpointPage from '../pages/CreateDataEndpointPage.vue'
import CreateModelEndpointPage from '../pages/CreateModelEndpointPage.vue'
import CreateModelEndpointPageOld from '../pages/CreateModelEndpointPageOld.vue'
import UpdatesPage from '../pages/UpdatesPage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/home',
    },
    {
      path: '/home',
      name: 'home',
      component: HomePage,
    },
    {
      path: '/endpoints',
      name: 'endpoints',
      component: EndpointsPage,
    },
    {
      path: '/datasets',
      name: 'datasets',
      component: DatasetsPage,
    },
    {
      path: '/models',
      name: 'models',
      component: ModelsPage,
    },
    {
      path: '/endpoints/:slug',
      name: 'endpoint-detail',
      component: EndpointDetailPage,
    },
    {
      path: '/datasets/:slug',
      name: 'dataset-detail',
      component: DatasetDetailPage,
    },
    {
      path: '/models/:slug',
      name: 'model-detail',
      component: ModelDetailPage,
    },
    {
      path: '/inbox',
      name: 'inbox',
      component: InboxPage,
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: AnalyticsPage,
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsPage,
    },
    {
      path: '/create/data-endpoint',
      name: 'create-data-endpoint',
      component: CreateDataEndpointPage,
    },
    {
      path: '/create/model-endpoint',
      name: 'create-model-endpoint',
      component: CreateModelEndpointPage,
    },
    {
      path: '/updates',
      name: 'updates',
      component: UpdatesPage,
    },
    {
      path: '/create/model-endpoint-old',
      name: 'create-model-endpoint-old',
      component: CreateModelEndpointPageOld,
    },
  ],
})

export default router
