import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import type { BenchmarkJob } from '@/api/types'

vi.mock('@/api/endpoints/benchmarks', () => ({ benchmarksApi: { listJobs: vi.fn() } }))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const { ACTIVE_POLL_MS, IDLE_POLL_MS, useBenchmarkJobs } = await import(
  '@/composables/useBenchmarkJobs'
)

const listJobs = vi.mocked(benchmarksApi.listJobs)

function job(state: BenchmarkJob['state']): BenchmarkJob {
  return {
    id: `job-${state}`,
    state,
    phase: 'evaluate',
    kind: 'pipeline',
    block: '',
    model: '',
    step_done: 0,
    step_total: 0,
    message: '',
    created_at: null,
    started_at: null,
    finished_at: null,
  }
}

function mountJobs() {
  const Host = defineComponent({
    setup() {
      const { jobs } = useBenchmarkJobs('ep')
      return () => h('div', jobs.value.map((j) => j.state).join(','))
    },
  })
  return mount(Host)
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  listJobs.mockReset()
})

describe('useBenchmarkJobs', () => {
  it('polls often while a job is active and slowly once every job has finished', async () => {
    listJobs.mockResolvedValue([job('running')])
    const wrapper = mountJobs()
    await flushPromises()
    expect(listJobs).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toBe('running')

    listJobs.mockResolvedValue([job('succeeded')])
    await vi.advanceTimersByTimeAsync(ACTIVE_POLL_MS)
    expect(listJobs).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toBe('succeeded')

    await vi.advanceTimersByTimeAsync(ACTIVE_POLL_MS * 3)
    expect(listJobs).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(IDLE_POLL_MS)
    expect(listJobs).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('stops polling when unmounted during the first request', async () => {
    let answer!: (jobs: BenchmarkJob[]) => void
    listJobs.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)))
    const wrapper = mountJobs()
    wrapper.unmount()
    answer([job('queued')])
    await flushPromises()
    await vi.advanceTimersByTimeAsync(IDLE_POLL_MS * 2)
    expect(listJobs).toHaveBeenCalledTimes(1)
  })
})
