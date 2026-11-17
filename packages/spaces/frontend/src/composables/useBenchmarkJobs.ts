import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkJob } from '@/api/types'

/** While a job is queued or running. */
export const ACTIVE_POLL_MS = 5000
/** While every job is finished: a run the schedule starts shows up within a minute. */
export const IDLE_POLL_MS = 60_000

/** Every job for one endpoint, polled while mounted: often while a job is active, slowly when none is. */
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

  const active = computed(() =>
    jobs.value.some((job) => job.state === 'queued' || job.state === 'running'),
  )

  function stop(): void {
    if (timer) clearInterval(timer)
    timer = undefined
  }

  // Stops with the component's scope, so a refresh that resolves after unmount starts no timer.
  watch(
    active,
    (on) => {
      stop()
      timer = setInterval(refresh, on ? ACTIVE_POLL_MS : IDLE_POLL_MS)
    },
    { immediate: true },
  )

  onMounted(refresh)
  onUnmounted(stop)

  return { jobs, refresh }
}
