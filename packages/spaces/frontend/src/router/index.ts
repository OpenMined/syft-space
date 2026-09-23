import { createRouter, createWebHashHistory } from 'vue-router'

// Pages are loaded on demand. Importing them eagerly puts every page, and
// everything they pull in, into the entry chunk — a single multi-megabyte
// response that a browser on a real network link has to finish before it
// can render anything.
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
      component: () => import('../pages/HomePage.vue'),
    },
    {
      path: '/endpoints',
      name: 'endpoints',
      component: () => import('../pages/EndpointsPage.vue'),
    },
    {
      path: '/datasets',
      name: 'datasets',
      component: () => import('../pages/DatasetsPage.vue'),
    },
    {
      path: '/models',
      name: 'models',
      component: () => import('../pages/ModelsPage.vue'),
    },
    {
      path: '/endpoints/:slug',
      name: 'endpoint-detail',
      component: () => import('../pages/EndpointDetailPage.vue'),
    },
    {
      path: '/datasets/:slug',
      name: 'dataset-detail',
      component: () => import('../pages/DatasetDetailPage.vue'),
    },
    {
      path: '/models/:slug',
      name: 'model-detail',
      component: () => import('../pages/ModelDetailPage.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../pages/ChatPage.vue'),
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('../pages/AnalyticsPage.vue'),
    },
    {
      path: '/benchmark',
      name: 'benchmark',
      component: () => import('../pages/BenchmarkPage.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../pages/SettingsPage.vue'),
    },
    {
      path: '/go-live',
      name: 'go-live',
      component: () => import('../pages/GoLivePage.vue'),
    },
    {
      path: '/create/data-endpoint',
      name: 'create-data-endpoint',
      component: () => import('../pages/CreateDataEndpointPage.vue'),
    },
    {
      path: '/updates',
      name: 'updates',
      component: () => import('../pages/UpdatesPage.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../pages/AboutPage.vue'),
    },
    {
      path: '/onboarding',
      name: 'onboarding',
      component: () => import('../pages/OnboardingPage.vue'),
    },
    {
      path: '/experimental-rwdt',
      name: 'experimental-remote-weaviate-dataset',
      component: () => import('../pages/ExperimentalRemoteWeaviateDatasetPage.vue'),
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
