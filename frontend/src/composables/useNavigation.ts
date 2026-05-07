import { useRouter } from 'vue-router'
import type { LocationQueryValue } from 'vue-router'

export interface NavigationRoute {
  name: string
  params?: Record<string, string | number>
  query?: Record<string, LocationQueryValue | LocationQueryValue[]>
}

export function useNavigation() {
  const router = useRouter()

  const routes = {
    liveDetail: (slug: string) => ({ name: 'endpoint-detail', params: { slug } }),
    goLive: { name: 'go-live' },
    models: { name: 'models' },
    modelDetail: (slug: string) => ({ name: 'model-detail', params: { slug } }),

    // Datasets
    datasets: { name: 'datasets' },
    datasetDetail: (slug: string) => ({ name: 'dataset-detail', params: { slug } }),

    // Other pages
    inbox: { name: 'inbox' },
    settings: { name: 'settings' },
    earnings: { name: 'earnings' },
  }

  // Helper methods for common navigation patterns
  const goToGoLive = () => navigateTo(routes.goLive)
  const goToEndpoints = () => navigateTo(routes.endpoints)
  const goToModels = () => navigateTo(routes.models)
  const goToDatasets = () => navigateTo(routes.datasets)
  const goToHome = () => navigateTo(routes.home)
  const goToInbox = () => navigateTo(routes.inbox)
  const goToSettings = () => navigateTo(routes.settings)
  const goToEarnings = () => navigateTo(routes.earnings)

  const goToEndpointDetail = (slug: string) => navigateTo(routes.endpointDetail(slug))
  const goToModelDetail = (slug: string) => navigateTo(routes.modelDetail(slug))
  const goToDatasetDetail = (slug: string) => navigateTo(routes.datasetDetail(slug))

  const goToCreateEndpoint = () => navigateTo(routes.createEndpoint)
  const goToCreateDataEndpoint = () => navigateTo(routes.createDataEndpoint)
  const goToCreateModelEndpoint = () => navigateTo(routes.createModelEndpoint)

  return {
    routes,
    goToGoLive,
    goToEndpoints,
    goToModels,
    goToDatasets,
    goToHome,
    goToInbox,
    goToSettings,
    goToEarnings,
    goToEndpointDetail,
    goToModelDetail,
    goToDatasetDetail,
    goToCreateEndpoint,
    goToCreateDataEndpoint,
    goToCreateModelEndpoint,
  }
}
