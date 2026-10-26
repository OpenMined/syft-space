import { onMounted, onUnmounted, ref } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkJob } from '@/api/types'

const POLL_MS = 5000

/** Every job for one endpoint, polled while mounted. */
export function useBenchmarkJobs(slug: string) {
  const jobs = ref<BenchmarkJob[]>([])
  let timer: ReturnType<typeof setInterval> | undefined

  async function refresh(): Promise<void> {
    try {
      jobs.value = await benchmarksApi.listJobs(slug)
    } catch {
      // Keep the last list on a failed poll.
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
