import { describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, nextTick, reactive, ref, shallowRef } from 'vue'
import { mount, RouterLinkStub } from '@vue/test-utils'
import type { BenchmarkRunProgress, BenchmarkRunSummary, BenchmarkTarget } from '@/api/types'
import { Select } from '@/components/ui/select'
import RunsList from '@/components/benchmark/report/RunsList.vue'
import { provideRunReport } from '@/components/benchmark/report/context'
import type { RunReport, RunsFilters } from '@/components/benchmark/report/useRunReport'
import { progress, runSummary } from './reportFixtures'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

function fakeReport(
  runs: BenchmarkRunSummary[],
  inProgress: BenchmarkRunProgress[] = [],
  target: Partial<BenchmarkTarget> | null = null,
) {
  const filters = reactive<RunsFilters>({ from: '', to: '', status: 'all' })
  return {
    inProgress: ref(inProgress),
    runs: ref(runs),
    total: ref(runs.length),
    page: ref(0),
    filters,
    filtered: computed(() => Boolean(filters.from || filters.to || filters.status !== 'all')),
    target: shallowRef(target),
    loading: ref(false),
    loaded: ref(true),
    error: ref<string | null>(null),
    refresh: vi.fn(),
  }
}

function mountList(report: ReturnType<typeof fakeReport>) {
  const Host = defineComponent({
    setup() {
      provideRunReport(report as unknown as RunReport)
      return () => h(RunsList, { slug: 'ep' })
    },
  })
  return mount(Host, { global: { stubs: { RouterLink: RouterLinkStub } } })
}

describe('RunsList', () => {
  it('lists an in-progress run first, with its progress and no link', () => {
    const report = fakeReport(
      [runSummary('done', { published: true })],
      [progress('live', { phase: 'evaluate', step_done: 3, step_total: 12 })],
    )
    const wrapper = mountList(report)

    const live = wrapper.get('[data-testid="run-in-progress"]')
    expect(live.text()).toContain('Step 3 of 12')
    expect(live.text()).toContain('Results when the run finishes')
    expect(live.text()).toContain('Running')
    expect(live.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('25')
    expect(live.findComponent(RouterLinkStub).exists()).toBe(false)

    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]!.attributes('data-testid')).toBe('run-in-progress')

    const done = wrapper.get('[data-testid="run-row"]')
    expect(done.text()).toContain('+47 to +70')
    expect(done.text()).toContain('Published')
    void done.trigger('click')
    expect(push).toHaveBeenCalledWith({ query: { tab: 'results', job: 'done' } })
  })

  it('shows Queued for a queued run and dashes for missing figures', () => {
    const report = fakeReport(
      [runSummary('old', { articles: null, lift_lo: null, lift_hi: null })],
      [progress('q', { state: 'queued', step_total: 0 })],
    )
    const wrapper = mountList(report)
    expect(wrapper.get('[data-testid="run-in-progress"]').text()).toContain('Queued')
    const old = wrapper.get('[data-testid="run-row"]')
    expect(old.findAll('td')[1]!.text()).toBe('—')
    expect(old.findAll('td')[4]!.text()).toBe('—')
  })

  it('passes the filters to the server-side list', async () => {
    const report = fakeReport([runSummary('a')])
    const wrapper = mountList(report)
    wrapper.findComponent(Select).vm.$emit('update:modelValue', 'published')
    await nextTick()
    expect(report.filters.status).toBe('published')
    await wrapper.get('[data-testid="filter-from"]').setValue('2026-09-26')
    await wrapper.get('[data-testid="filter-to"]').setValue('2026-09-30')
    expect(report.filters).toMatchObject({ from: '2026-09-26', to: '2026-09-30' })
  })

  it('says when no runs match the filters', async () => {
    const report = fakeReport([])
    const wrapper = mountList(report)
    expect(wrapper.get('[data-testid="runs-empty"]').text()).toBe('No runs yet.')
    report.filters.from = '2026-09-26'
    await nextTick()
    expect(wrapper.get('[data-testid="runs-empty"]').text()).toContain(
      'No runs match these filters',
    )
  })

  it('always shows the count of runs, with paging disabled on one page', () => {
    const wrapper = mountList(fakeReport([runSummary('a'), runSummary('b')]))
    const pager = wrapper.get('[data-testid="pager"]')
    expect(pager.text()).toContain('Showing 1–2 of 2 runs')
    expect(pager.findAll('button').every((b) => b.attributes('disabled') !== undefined)).toBe(true)
  })

  it('pages finished runs on the server', async () => {
    const report = fakeReport(Array.from({ length: 25 }, (_, i) => runSummary(`r${i}`)))
    report.total.value = 30
    const wrapper = mountList(report)
    expect(wrapper.get('[data-testid="pager"]').text()).toContain('Showing 1–25 of 30 runs')

    const next = wrapper.findAll('[data-testid="pager"] button').find((b) => b.text() === 'Next')!
    await next.trigger('click')
    expect(report.page.value).toBe(1)
    report.runs.value = report.runs.value.slice(0, 5)
    await nextTick()
    expect(wrapper.get('[data-testid="pager"]').text()).toContain('Showing 26–30 of 30 runs')
  })

  it('shows the schedule, loading and error states', async () => {
    const report = fakeReport([], [], {
      schedule: '24h',
      schedule_at: '06:00',
      next_run_at: null,
      probe: { document_window_days: 1 },
    })
    report.loading.value = true
    report.loaded.value = false
    const wrapper = mountList(report)
    expect(wrapper.get('[data-testid="schedule"]').text()).toBe(
      'One run a day at 06:00, on the articles you published in the previous 24 hours.',
    )
    expect(wrapper.find('[data-testid="runs-loading"]').exists()).toBe(true)

    report.loading.value = false
    report.error.value = 'Could not load benchmark runs'
    await nextTick()
    expect(wrapper.get('[data-testid="runs-error"]').text()).toContain('Could not load')
    expect(wrapper.get('[data-testid="runs-empty"]').text()).toBe('No runs yet.')
    await wrapper.get('[data-testid="runs-error"] button').trigger('click')
    expect(report.refresh).toHaveBeenCalled()
  })

  it('omits the schedule sentence when nothing runs on a schedule', () => {
    const wrapper = mountList(fakeReport([], [], { schedule: '', next_run_at: null, probe: {} }))
    expect(wrapper.find('[data-testid="schedule"]').exists()).toBe(false)
  })
})
