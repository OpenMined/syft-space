/** How many articles the benchmark counts in the time window, refetched as the window is edited. */
import { onBeforeUnmount, ref, watch } from 'vue'

import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { windowDaysParam } from './setupForm'

const DEBOUNCE_MS = 400

export function useArticleWindow(slug: string, windowDays: () => number | undefined) {
  const articles = ref<number | null>(null)
  // Only the latest request may write its answer.
  let latest = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  async function reload(): Promise<void> {
    const ask = ++latest
    try {
      const found = await benchmarksApi.getWindow(slug, windowDaysParam(windowDays()))
      if (ask === latest) articles.value = found.count
    } catch {
      if (ask === latest) articles.value = null
    }
  }

  watch(windowDays, (_days, before) => {
    // The first value arrives with the loaded form, not from an edit.
    if (before === undefined) return
    clearTimeout(timer)
    timer = setTimeout(() => void reload(), DEBOUNCE_MS)
  })

  onBeforeUnmount(() => clearTimeout(timer))

  return { articles, reload }
}
