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
import UpdatesPage from '../pages/UpdatesPage.vue'
import OnboardingPage from '../pages/OnboardingPage.vue'
import ExperimentalRemoteWeaviateDatasetPage from '../pages/ExperimentalRemoteWeaviateDatasetPage.vue'
import { marketplacesApi } from '../api/endpoints/marketplaces'

let onboardingStatusCache: boolean | null = null

export async function checkOnboardingStatus(): Promise<boolean> {
  if (onboardingStatusCache !== null) {
    return onboardingStatusCache
  }
  try {
    const marketplaces = await marketplacesApi.list()
    onboardingStatusCache = marketplaces.length > 0
    return onboardingStatusCache
  } catch {
    // If API fails, assume not onboarded
    return false
  }
}

export function clearOnboardingCache() {
  onboardingStatusCache = null
}

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
      path: '/onboarding',
      name: 'onboarding',
      component: OnboardingPage,
    },
    {
      path: '/experimental-rwdt',
      name: 'experimental-remote-weaviate-dataset',
      component: ExperimentalRemoteWeaviateDatasetPage,
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  // Extract authToken from URL hash params and save to localStorage
  if (to.query.authToken) {
    localStorage.setItem('authToken', to.query.authToken as string)
    const { authToken: _authToken, ...remainingQuery } = to.query
    next({ ...to, query: remainingQuery, replace: true })
    return
  }

  // Skip onboarding check for the onboarding page itself
  if (to.name === 'onboarding') {
    next()
    return
  }

  const isOnboarded = await checkOnboardingStatus()
  if (!isOnboarded) {
    // Preserve the original destination URL
    const nextUrl = to.fullPath !== '/' ? to.fullPath : undefined
    next({
      name: 'onboarding',
      query: nextUrl ? { next: nextUrl } : undefined,
    })
    return
  }
  next()
})

export default router
