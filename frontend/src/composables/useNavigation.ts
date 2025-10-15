/**
 * Composable for standardized navigation patterns
 * Provides consistent routing and navigation helpers
 */

import { useRouter } from 'vue-router'

export interface NavigationRoute {
  name: string
  params?: Record<string, any>
  query?: Record<string, any>
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

  // Standard route definitions for consistency
  const routes = {
    home: { name: 'home' },
    
    // Endpoints
    endpoints: { name: 'endpoints' },
    endpointDetail: (slug: string) => ({ name: 'endpoint-detail', params: { slug } }),
    createEndpoint: { name: 'create-endpoint' },
    createDataEndpoint: { name: 'create-data-endpoint' },
    createModelEndpoint: { name: 'create-model-endpoint' },
    
    // Models  
    models: { name: 'models' },
    modelDetail: (slug: string) => ({ name: 'model-detail', params: { slug } }),
    
    // Datasets
    datasets: { name: 'datasets' },
    datasetDetail: (slug: string) => ({ name: 'dataset-detail', params: { slug } }),
    
    // Other pages
    inbox: { name: 'inbox' },
    settings: { name: 'settings' }
  }

  // Helper methods for common navigation patterns
  const goToEndpoints = () => navigateTo(routes.endpoints)
  const goToModels = () => navigateTo(routes.models)
  const goToDatasets = () => navigateTo(routes.datasets)
  const goToHome = () => navigateTo(routes.home)
  const goToInbox = () => navigateTo(routes.inbox)
  const goToSettings = () => navigateTo(routes.settings)

  const goToEndpointDetail = (slug: string) => navigateTo(routes.endpointDetail(slug))
  const goToModelDetail = (slug: string) => navigateTo(routes.modelDetail(slug))
  const goToDatasetDetail = (slug: string) => navigateTo(routes.datasetDetail(slug))

  const goToCreateEndpoint = () => navigateTo(routes.createEndpoint)
  const goToCreateDataEndpoint = () => navigateTo(routes.createDataEndpoint)
  const goToCreateModelEndpoint = () => navigateTo(routes.createModelEndpoint)

  return {
    // Core navigation
    navigateTo,
    goBack,
    routes,
    
    // Helper methods
    goToEndpoints,
    goToModels,
    goToDatasets,
    goToHome,
    goToInbox,
    goToSettings,
    goToEndpointDetail,
    goToModelDetail,
    goToDatasetDetail,
    goToCreateEndpoint,
    goToCreateDataEndpoint,
    goToCreateModelEndpoint
  }
}