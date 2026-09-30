import { computed, onMounted, onUnmounted, ref } from 'vue'
import { blockWords, phaseWords } from '@/components/benchmark/labels'
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
 * it goes — the phase, what is being done to the question, the model, which
 * question within the pass and which pass within the whole launch.
 *
 * The phase leads, because it is the one part that always exists and the one
 * an owner asks for first: a launch that has been going for an hour is a
 * different thing depending on whether it is still building questions or is
 * on the fourth of six passes. Generation, filtering and judging report no
 * pass at all — they have no notion of one — and then this is the phase
 * alone rather than nothing.
 */
function runningDetail(job: BenchmarkJob): string {
  const parts: string[] = []
  const phase = phaseWords(job.phase)
  if (phase) parts.push(phase)
  if (job.block) parts.push(blockWords(job.block))
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
    case 'running': {
      // The message is what the phase itself last said — a count, a line of
      // outcome — and the detail is where the launch is. Both, when both
      // exist: one without the other reads as either a figure from nowhere
      // or a position with nothing to show for it.
      const detail = runningDetail(job)
      if (job.message && detail) return `${detail} · ${job.message}`
      return job.message || detail || 'Running'
    }
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
