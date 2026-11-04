/**
 * Feature flags. The backend owns them (AppSettings, e.g. SYFT_BENCHMARK_ENABLED);
 * the router loads them before the first page renders, so pages read them
 * synchronously. Every flag is off until the backend turns it on, so a hidden
 * feature never flashes into view.
 */

import { reactive } from 'vue'
import { settingsApi } from '@/api/endpoints/settings'

export const features = reactive({
  benchmark: false,
})

let loaded: Promise<void> | null = null

/** Load the flags once; a failed load is retried on the next call. */
export function loadFeatures(): Promise<void> {
  loaded ??= settingsApi.getFeatures().then(
    (res) => {
      features.benchmark = res.benchmark
    },
    () => {
      loaded = null
    },
  )
  return loaded
}
