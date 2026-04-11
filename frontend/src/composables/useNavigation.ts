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
    dataSourceDetail: (slug: string) => ({ name: 'dataset-detail', params: { slug } }),
  }

  const goToGoLive = () => router.push(routes.goLive)
  const goToModels = () => router.push(routes.models)

  return {
    routes,
    goToGoLive,
    goToModels,
  }
}
