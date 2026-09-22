/**
 * The model catalogue of one benchmark, fetched once and shared.
 *
 * Whole rather than queried per keystroke: the list changes only when its owner
 * asks the benchmark to refresh, and a request between the typing and the list
 * is the delay that sends people back to writing model names by hand.
 *
 * The cache is module-level and keyed by connection, so four pickers on one
 * form ask once and it survives the popover opening and closing.
 */
import { ref } from 'vue'

import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkModelCatalog } from '@/api/types'
import { apiErrorDetail } from '@/lib/errors'

const EMPTY: BenchmarkModelCatalog = {
  models: [],
  vendors: [],
  pins: {},
  fetched: {},
  total: 0,
}

const cache = new Map<string, BenchmarkModelCatalog>()
// The request in flight, so that four pickers opening at once make one call.
const inFlight = new Map<string, Promise<BenchmarkModelCatalog>>()

export function useModelCatalog() {
  const catalog = ref<BenchmarkModelCatalog>(EMPTY)
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref<string | null>(null)

  /** Load the catalogue, from the cache when it is already here. */
  const load = async (connectionId: string): Promise<void> => {
    if (!connectionId) return

    const held = cache.get(connectionId)
    if (held) {
      catalog.value = held
      return
    }

    loading.value = true
    error.value = null
    try {
      let pending = inFlight.get(connectionId)
      if (!pending) {
        pending = benchmarksApi.listModels(connectionId)
        inFlight.set(connectionId, pending)
      }
      const data = await pending
      cache.set(connectionId, data)
      catalog.value = data
    } catch (err) {
      // Not fatal: without a catalogue the picker still takes a typed name.
      error.value = apiErrorDetail(err, 'The model list could not be loaded')
    } finally {
      inFlight.delete(connectionId)
      loading.value = false
    }
  }

  /** Have the benchmark fetch its provider's list afresh. */
  const refresh = async (connectionId: string): Promise<boolean> => {
    if (!connectionId) return false

    refreshing.value = true
    error.value = null
    try {
      const data = await benchmarksApi.refreshModels(connectionId)
      cache.set(connectionId, data)
      catalog.value = data
      return true
    } catch (err) {
      // The benchmark's own words: a perimeter that forbids the call names
      // the host to open, which is an instruction, not a failure message.
      error.value = apiErrorDetail(err, 'The model list could not be refreshed')
      return false
    } finally {
      refreshing.value = false
    }
  }

  return { catalog, loading, refreshing, error, load, refresh }
}
