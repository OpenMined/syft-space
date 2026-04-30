import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import EndpointsPage from '../pages/EndpointsPage.vue'
import DatasetsPage from '../pages/DatasetsPage.vue'
import ModelsPage from '../pages/ModelsPage.vue'
import InboxPage from '../pages/InboxPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import AnalyticsPage from '../pages/AnalyticsPage.vue'
import EarningsPage from '../pages/EarningsPage.vue'
import EndpointDetailPage from '../pages/EndpointDetailPage.vue'
import DatasetDetailPage from '../pages/DatasetDetailPage.vue'
import ModelDetailPage from '../pages/ModelDetailPage.vue'
import CreateDataEndpointPage from '../pages/CreateDataEndpointPage.vue'
import CreateModelEndpointPage from '../pages/CreateModelEndpointPage.vue'
import UpdatesPage from '../pages/UpdatesPage.vue'
import AboutPage from '../pages/AboutPage.vue'
import OnboardingPage from '../pages/OnboardingPage.vue'
import ExperimentalRemoteWeaviateDatasetPage from '../pages/ExperimentalRemoteWeaviateDatasetPage.vue'
import { marketplacesApi } from '../api/endpoints/marketplaces'
import { settingsApi } from '../api/endpoints/settings'
import { useServerAvailabilityStore } from '../stores/serverAvailability'

let onboardingStatusCache: boolean | null = null

export async function checkOnboardingStatus(): Promise<boolean> {
  if (onboardingStatusCache !== null) {
    return onboardingStatusCache
  }
  try {
    const marketplaces = await marketplacesApi.list()
    if (marketplaces.length === 0) {
      onboardingStatusCache = false
      return false
    }

    // Marketplace exists — also verify network is configured
    const publicUrlResponse = await settingsApi.getPublicUrl()
    onboardingStatusCache = publicUrlResponse.public_url !== null
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
      path: '/earnings',
      name: 'earnings',
      component: EarningsPage,
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
      path: '/about',
      name: 'about',
      component: AboutPage,
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
  // Extract connection params from URL query and save to sessionStorage
  const { authToken, host, port, ...remainingQuery } = to.query
  let paramsExtracted = false

  if (authToken) {
    localStorage.setItem('authToken', authToken as string)
    paramsExtracted = true
  }
  if (host) {
    sessionStorage.setItem('host', host as string)
    paramsExtracted = true
  }
  if (port) {
    sessionStorage.setItem('port', port as string)
    paramsExtracted = true
  }

  if (paramsExtracted) {
    next({ ...to, query: remainingQuery, replace: true })
    return
  }

  // Skip server readiness and onboarding checks for standalone windows
  if (to.name === 'updates' || to.name === 'about') {
    next()
    return
  }

  // Wait for backend to be available before checking onboarding
  const serverStore = useServerAvailabilityStore()
  serverStore.startPolling()
  await serverStore.waitUntilReady()

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
