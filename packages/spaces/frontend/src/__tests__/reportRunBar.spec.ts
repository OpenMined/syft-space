import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, nextTick, ref, shallowRef } from 'vue'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { BenchmarkRunProgress, BenchmarkRunReport, BenchmarkRunSummary } from '@/api/types'
import { Select } from '@/components/ui/select'
import ReportRunBar from '@/components/benchmark/report/ReportRunBar.vue'
import {
  provideRun,
  provideRunReport,
  type RunContext,
} from '@/components/benchmark/report/context'
import type { RunReport } from '@/components/benchmark/report/useRunReport'
import { progress, runReport, runSummary } from './reportFixtures'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const toast = vi.hoisted(() => ({
  success: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  error: vi.fn(),
}))
vi.mock('vue-sonner', () => ({ toast }))

const REFUSED = {
  marketplace_id: 'm1',
  marketplace_name: 'Syft Hub',
  success: false,
  supported: true,
  message: null,
  error: 'offline',
}

function fakeReport(runs: BenchmarkRunSummary[], inProgress: BenchmarkRunProgress[] = []) {
  return {
    runs: ref(runs),
    inProgress: ref(inProgress),
    publish: vi.fn(),
    unpublish: vi.fn(),
    downloadSummary: vi.fn(async () => {}),
  }
}

function fakeRun(summary: BenchmarkRunSummary | null) {
  const data = shallowRef<BenchmarkRunReport | null>(summary ? runReport({ run: summary }) : null)
  const run: RunContext = {
    jobId: 'j1',
    data,
    loading: ref(false),
    error: ref(null),
    running: computed(() => false),
    model: computed(() => 'm1'),
    modelReport: computed(() => null),
    selectModel: vi.fn(),
    kind: ref(null),
    setKind: vi.fn(),
    reload: vi.fn(async () => {}),
  }
  return run
}

function mountBar(
  report: ReturnType<typeof fakeReport>,
  run: RunContext = fakeRun(runSummary('j1')),
  jobId = 'j1',
) {
  const Host = defineComponent({
    setup() {
      provideRunReport(report as unknown as RunReport)
      provideRun(run)
      return () => h(ReportRunBar, { slug: 'ep', jobId, modelId: 'm1' })
    },
  })
  return mount(Host, { global: { stubs: { RouterLink: RouterLinkStub } } })
}

beforeEach(() => vi.clearAllMocks())

describe('ReportRunBar', () => {
  it('publishes a private run, then offers to unpublish it', async () => {
    const report = fakeReport([runSummary('j1')])
    const run = fakeRun(runSummary('j1'))
    report.publish.mockImplementation(async () => {
      run.data.value = runReport({ run: runSummary('j1', { published: true }) })
      return { refused: [] }
    })
    report.unpublish.mockResolvedValue({ refused: [] })
    const wrapper = mountBar(report, run)

    expect(wrapper.get('[data-testid="visibility"]').text()).toBe(
      'Private, only your team can see it',
    )
    await wrapper.get('[data-testid="publish"]').trigger('click')
    await flushPromises()
    expect(report.publish).toHaveBeenCalledWith('j1')
    expect(toast.success).toHaveBeenCalledWith('Published')
    expect(wrapper.get('[data-testid="visibility"]').text()).toBe('Published')

    await wrapper.get('[data-testid="unpublish"]').trigger('click')
    await flushPromises()
    expect(report.unpublish).toHaveBeenCalledWith('j1')
    expect(toast.success).toHaveBeenCalledWith('Unpublished')
  })

  it('reports a refused unpublish with the server’s reason', async () => {
    const report = fakeReport([])
    report.unpublish.mockRejectedValue({
      response: { data: { detail: 'This run is not the published one' } },
    })
    const wrapper = mountBar(report, fakeRun(runSummary('j1', { published: true })))
    await wrapper.get('[data-testid="unpublish"]').trigger('click')
    await flushPromises()
    expect(toast.error).toHaveBeenCalledWith('This run is not the published one')
    expect(wrapper.get('[data-testid="unpublish"]').attributes('disabled')).toBeUndefined()
  })

  it('names the marketplaces that refused', async () => {
    const report = fakeReport([runSummary('j1')])
    report.publish.mockResolvedValue({ refused: [REFUSED] })
    const wrapper = mountBar(report)
    await wrapper.get('[data-testid="publish"]').trigger('click')
    await flushPromises()
    expect(toast.warning).toHaveBeenCalledWith('Published here; 1 marketplace(s) refused', {
      description: 'Syft Hub: offline',
    })
  })

  it('offers to republish an outdated card', async () => {
    const report = fakeReport([])
    report.publish.mockResolvedValue({ refused: [] })
    const wrapper = mountBar(
      report,
      fakeRun(runSummary('j1', { published: true, card_outdated: true })),
    )
    expect(wrapper.get('[data-testid="card-outdated"]').text()).toContain('out of date')
    await wrapper.get('[data-testid="republish"]').trigger('click')
    await flushPromises()
    expect(report.publish).toHaveBeenCalledWith('j1')
  })

  it('hides the outdated note on a private run', () => {
    const wrapper = mountBar(fakeReport([]), fakeRun(runSummary('j1', { card_outdated: true })))
    expect(wrapper.find('[data-testid="card-outdated"]').exists()).toBe(false)
  })

  it('downloads the summary', async () => {
    const report = fakeReport([runSummary('j1')])
    const wrapper = mountBar(report)
    await wrapper.get('[data-testid="download-summary"]').trigger('click')
    await flushPromises()
    expect(report.downloadSummary).toHaveBeenCalledWith('j1')
  })

  it('shows a note and no actions for a run in progress', async () => {
    const report = fakeReport([], [progress('j1', { phase: 'evaluate' })])
    const wrapper = mountBar(report, fakeRun(null))
    await nextTick()
    expect(wrapper.get('[data-testid="running-note"]').text()).toContain('question 3 of 12')
    expect(wrapper.get('[data-testid="publish"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="download-summary"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="visibility"]').exists()).toBe(false)
  })

  it('opens the run picked, keeping the model', () => {
    const report = fakeReport([runSummary('j1'), runSummary('j0')])
    const wrapper = mountBar(report)
    const select = wrapper.findComponent(Select)
    select.vm.$emit('update:modelValue', 'j0')
    expect(push).toHaveBeenCalledWith({ query: { tab: 'results', job: 'j0', model: 'm1' } })
  })

  it('links back to the runs list', () => {
    const wrapper = mountBar(fakeReport([runSummary('j1')]))
    expect(wrapper.getComponent(RouterLinkStub).props('to')).toEqual({ query: { tab: 'results' } })
  })
})
