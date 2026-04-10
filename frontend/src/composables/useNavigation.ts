/**
 * Composable for standardized navigation patterns
 * Provides consistent routing and navigation helpers
 */

import { useRouter } from 'vue-router'
import type { LocationQueryValue } from 'vue-router'

export interface NavigationRoute {
  name: string
  params?: Record<string, string | number>
  query?: Record<string, LocationQueryValue | LocationQueryValue[]>
}

export function useNavigation() {
  const router = useRouter()

  // Standard navigation methods
  const navigateTo = (route: NavigationRoute | string) => {
    if (typeof route === 'string') {
      router.push(route)
    } else {
      router.push(route)
    }
  }

  const goBack = (fallbackRoute: NavigationRoute) => {
    // Use browser back if available, otherwise fallback to specified route
    if (window.history.length > 1) {
      router.go(-1)
    } else {
      navigateTo(fallbackRoute)
    }
  }

  const routes = {
    home: { name: 'home' },

    // APIs (was: Endpoints)
    live: { name: 'endpoints' },
    liveDetail: (slug: string) => ({ name: 'endpoint-detail', params: { slug } }),
    goLive: { name: 'go-live' },
    createDataEndpoint: { name: 'create-data-endpoint' },

    // Models
    models: { name: 'models' },
    modelDetail: (slug: string) => ({ name: 'model-detail', params: { slug } }),

    // Data Sources (was: Datasets)
    dataSources: { name: 'datasets' },
    dataSourceDetail: (slug: string) => ({ name: 'dataset-detail', params: { slug } }),

    // Other pages
    inbox: { name: 'inbox' },
    analytics: { name: 'analytics' },
    settings: { name: 'settings' },

    // Aliases for backwards compat
    endpoints: { name: 'endpoints' },
    datasets: { name: 'datasets' },
    endpointDetail: (slug: string) => ({ name: 'endpoint-detail', params: { slug } }),
    datasetDetail: (slug: string) => ({ name: 'dataset-detail', params: { slug } }),
  }

  const goToHome = () => navigateTo(routes.home)
  const goToLive = () => navigateTo(routes.live)
  const goToModels = () => navigateTo(routes.models)
  const goToDataSources = () => navigateTo(routes.dataSources)
  const goToInbox = () => navigateTo(routes.inbox)
  const goToAnalytics = () => navigateTo(routes.analytics)
  const goToSettings = () => navigateTo(routes.settings)

  const goToLiveDetail = (slug: string) => navigateTo(routes.liveDetail(slug))
  const goToModelDetail = (slug: string) => navigateTo(routes.modelDetail(slug))
  const goToDataSourceDetail = (slug: string) => navigateTo(routes.dataSourceDetail(slug))

  const goToGoLive = () => navigateTo(routes.goLive)
  const goToCreateDataEndpoint = () => navigateTo(routes.createDataEndpoint)

  // Backwards-compatible aliases
  const goToEndpoints = goToLive
  const goToDatasets = goToDataSources
  const goToEndpointDetail = (slug: string) => goToLiveDetail(slug)
  const goToDatasetDetail = (slug: string) => goToDataSourceDetail(slug)

  return {
    navigateTo,
    goBack,
    routes,

    goToHome,
    goToLive,
    goToModels,
    goToDataSources,
    goToInbox,
    goToAnalytics,
    goToSettings,
    goToLiveDetail,
    goToModelDetail,
    goToDataSourceDetail,
    goToGoLive,
    goToCreateDataEndpoint,

    // Backwards-compatible aliases
    goToEndpoints,
    goToDatasets,
    goToEndpointDetail,
    goToDatasetDetail,
  }
}
