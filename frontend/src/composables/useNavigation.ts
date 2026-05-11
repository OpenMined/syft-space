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
    home: { name: 'home' },
    endpoints: { name: 'endpoints' },
    endpointDetail: (slug: string) => ({ name: 'endpoint-detail', params: { slug } }),
    goLive: { name: 'go-live' },
    models: { name: 'models' },
    modelDetail: (slug: string) => ({ name: 'model-detail', params: { slug } }),
    datasets: { name: 'datasets' },
    datasetDetail: (slug: string) => ({ name: 'dataset-detail', params: { slug } }),
    createDataEndpoint: { name: 'create-data-endpoint' },
    settings: { name: 'settings' },
    earnings: { name: 'earnings' },
  } satisfies Record<string, NavigationRoute | ((slug: string) => NavigationRoute)>

  const navigateTo = (route: NavigationRoute) => router.push(route)

  const goToHome = () => navigateTo(routes.home)
  const goToEndpoints = () => navigateTo(routes.endpoints)
  const goToGoLive = () => navigateTo(routes.goLive)
  const goToModels = () => navigateTo(routes.models)
  const goToDatasets = () => navigateTo(routes.datasets)
  const goToSettings = () => navigateTo(routes.settings)
  const goToEarnings = () => navigateTo(routes.earnings)

  const goToEndpointDetail = (slug: string) => navigateTo(routes.endpointDetail(slug))
  const goToModelDetail = (slug: string) => navigateTo(routes.modelDetail(slug))
  const goToDatasetDetail = (slug: string) => navigateTo(routes.datasetDetail(slug))

  const goToCreateDataEndpoint = () => navigateTo(routes.createDataEndpoint)

  return {
    routes,
    navigateTo,
    goToHome,
    goToEndpoints,
    goToGoLive,
    goToModels,
    goToDatasets,
    goToSettings,
    goToEarnings,
    goToEndpointDetail,
    goToModelDetail,
    goToDatasetDetail,
    goToCreateDataEndpoint,
  }
}
