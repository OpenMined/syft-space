import { computed, onMounted, onUnmounted, ref } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkJob } from '@/api/types'

// A phase runs for minutes to hours, so this is watching for a state change,
// not for a number to tick — no reason to ask more often than that.
const POLL_MS = 5000

/** Every job for one endpoint, polled while any of them is still running. */
export function useBenchmarkJobs(slug: string) {
  const jobs = ref<BenchmarkJob[]>([])
  let timer: ReturnType<typeof setInterval> | undefined

  const running = computed(() =>
    jobs.value.some((job) => job.state === 'queued' || job.state === 'running'),
  )

  async function refresh(): Promise<void> {
    try {
      jobs.value = await benchmarksApi.listJobs(slug)
    } catch {
      // A blink in the control API must not wipe the progress the owner is
      // watching.
    }
  }

  function latestOf(kind: string): BenchmarkJob | undefined {
    return jobs.value.find((job) => job.kind === kind)
  }

  onMounted(async () => {
    await refresh()
    timer = setInterval(refresh, POLL_MS)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { jobs, running, refresh, latestOf }
}

/**
 * What a running job is doing right now, from the fields a pass reports as
 * it goes — model, which question within the pass, which pass within the
 * whole run. Generation, filtering and judging leave all three blank (they
 * have no notion of a "pass"), so this reads as an empty string for them and
 * `jobStateWords` falls back to the plain state word.
 */
function runningDetail(job: BenchmarkJob): string {
  const parts: string[] = []
  if (job.model) parts.push(job.model)
  if (job.step_total) parts.push(`question ${job.step_done} of ${job.step_total}`)
  if (job.total) parts.push(`pass ${job.done + 1} of ${job.total}`)
  return parts.join(' · ')
}

export function jobStateWords(job: BenchmarkJob | undefined): string {
  if (!job) return ''
  switch (job.state) {
    case 'queued':
      return 'Queued'
    case 'running':
      return job.message || runningDetail(job) || 'Running'
    case 'succeeded':
      return job.error ? `Done, with notes: ${job.error}` : 'Done'
    case 'failed':
      return `Failed: ${job.error || 'no details given'}`
    case 'cancelled':
      return 'Stopped'
    default:
      return job.state
  }
}
