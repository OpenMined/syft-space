import { onMounted, onUnmounted, ref } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkJob } from '@/api/types'

// A phase runs for minutes to hours, so this is watching for a state change,
// not for a number to tick — no reason to ask more often than that.
const POLL_MS = 5000

/** Every job for one endpoint, polled while any of them is still running. */
export function useBenchmarkJobs(slug: string) {
  const jobs = ref<BenchmarkJob[]>([])
  let timer: ReturnType<typeof setInterval> | undefined

  async function refresh(): Promise<void> {
    try {
      jobs.value = await benchmarksApi.listJobs(slug)
    } catch {
      // A blink in the control API must not wipe the progress the owner is
      // watching.
    }
  }

  onMounted(async () => {
    await refresh()
    timer = setInterval(refresh, POLL_MS)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { jobs, refresh }
}
