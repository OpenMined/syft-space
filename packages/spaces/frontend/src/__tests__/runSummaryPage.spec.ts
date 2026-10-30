import { describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, shallowRef } from 'vue'
import { mount, RouterLinkStub } from '@vue/test-utils'
import type { BenchmarkRunReport } from '@/api/types'
import RunSummaryPage from '@/components/benchmark/report/RunSummaryPage.vue'
import { provideRun, provideRunReport } from '@/components/benchmark/report/context'
import type { RunReport } from '@/components/benchmark/report/useRunReport'
import { useDetails } from '@/components/benchmark/report/details/useDetails'
import { hintText } from './hint'
import { GPT, OPUS, QWEN, modelReport, runReport, runSummary } from './reportFixtures'

const toast = vi.hoisted(() => ({ error: vi.fn(), warning: vi.fn() }))
vi.mock('vue-sonner', () => ({ toast }))
const saveRunExport = vi.hoisted(() => vi.fn(async () => {}))
vi.mock('@/components/benchmark/report/useRunReport', () => ({ saveRunExport }))

function mountPage(report: BenchmarkRunReport) {
  const data = shallowRef<BenchmarkRunReport | null>(report)
  const actions = {
    downloadSummary: vi.fn(async () => {}),
  }
  const Host = defineComponent({
    setup() {
      provideRunReport(actions as unknown as RunReport)
      provideRun({
        jobId: 'j1',
        slug: 'ep',
        data,
        model: computed(() => null),
        modelReport: computed(() => null),
      })
      return () => h(RunSummaryPage)
    },
  })
  const wrapper = mount(Host, { global: { stubs: { RouterLink: RouterLinkStub } } })
  return { wrapper, actions }
}

describe('RunSummaryPage', () => {
  it('shows the title, the article dates and the funnel', () => {
    const { wrapper } = mountPage(
      runReport({
        run: runSummary('j1', {
          questions: 23,
          articles: 10,
          articles_first: '2025-10-05',
          articles_last: '2025-10-09',
          articles_dated: 10,
          articles_new: 4,
        }),
        method: { ...runReport().method, web_check_model: GPT },
        funnel: { written: 1000, removed: {}, asked: 100, trick: 4 },
      }),
    )
    expect(wrapper.get('h1').text()).toMatch(/^Run of 30 Sep 2026, \d{2}:\d{2}$/)
    expect(wrapper.text()).not.toMatch(/Private|Published|Publish/)
    expect(wrapper.get('[data-testid="run-articles"]').text()).toBe(
      '23 questions from 10 articles published 5–9 Oct 2025 · 4 new this run',
    )
    const funnel = wrapper.get('[data-testid="funnel"]').text()
    expect(funnel).toContain('1,000 questions written')
    // The web check ran and removed nothing.
    expect(wrapper.get('[data-testid="funnel-removed"]').text()).toBe('0')
    expect(funnel).toContain('100 asked to each model')
  })

  it('shows only what is known about the articles and the funnel', () => {
    const { wrapper } = mountPage(
      runReport({
        run: runSummary('j1', { articles: null, questions: null, window_days: null }),
        funnel: { written: 1000, removed: { web_answerable: 900 }, asked: 100, trick: 0 },
      }),
    )
    expect(wrapper.find('[data-testid="run-articles"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="funnel-removed"]').text()).toBe('900')
  })

  it('shows dashes for a run that reused earlier questions', () => {
    const { wrapper } = mountPage(
      runReport({
        method: { ...runReport().method, web_check_model: GPT },
        funnel: { written: null, removed: {}, asked: 100, trick: 0 },
      }),
    )
    expect(wrapper.get('[data-testid="funnel"]').text()).toContain('— questions written')
    expect(wrapper.get('[data-testid="funnel-removed"]').text()).toBe('—')
  })

  it('shows a dash for the web check when none ran', () => {
    const { wrapper } = mountPage(
      runReport({ funnel: { written: 120, removed: {}, asked: 100, trick: 0 } }),
    )
    expect(wrapper.get('[data-testid="funnel-removed"]').text()).toBe('—')
  })

  it('never shows the run window as article dates', () => {
    const { wrapper } = mountPage(
      runReport({ run: runSummary('j1', { questions: 3, articles: 1 }) }),
    )
    expect(wrapper.get('[data-testid="run-articles"]').text()).toBe('3 questions from 1 article')
  })

  it('lists each model with both scores and links to it', () => {
    const { wrapper } = mountPage(
      runReport({
        models: [
          modelReport(OPUS),
          modelReport(QWEN, { right_with: 85, graded_with: 100, right_alone: 38, lift: 47 }),
        ],
      }),
    )
    expect(wrapper.get('[data-testid="models-lead"]').text()).toBe(
      'Your data added 47 to 50 points. Select a model to see how it answered.',
    )
    const rows = wrapper.findAll('[data-testid="model-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('Claude Opus 4.8')
    expect(rows[0]!.text()).toContain('Anthropic')
    expect(rows[0]!.get('[data-testid="right-with"]').text()).toBe('80 of 97 right with your data')
    expect(rows[0]!.get('[data-testid="right-alone"]').text()).toBe('30 of 100 on its own')
    expect(rows[0]!.text()).toContain('+50')
    expect(rows[1]!.findComponent(RouterLinkStub).props('to')).toEqual({
      query: { tab: 'results', job: 'j1', model: QWEN },
    })
    const method = wrapper.get('[data-testid="method-link"]')
    expect(method.text()).toContain('How this was tested')
    expect(method.findComponent(RouterLinkStub).props('to')).toEqual({
      query: { tab: 'results', job: 'j1', screen: 'method' },
    })
  })

  it('names why a model failed', async () => {
    const detail = '16 answers failed: the provider refused the request (invalid request (400)).'
    const { wrapper } = mountPage(
      runReport({
        models: [
          modelReport(OPUS),
          modelReport(QWEN, {
            graded_alone: 0,
            graded_with: 0,
            failure: { label: 'Request refused', detail },
          }),
        ],
      }),
    )
    const rows = wrapper.findAll('[data-testid="model-row"]')
    expect(rows[0]!.find('[data-testid="model-failure"]').exists()).toBe(false)
    const badge = rows[1]!.get('[data-testid="model-failure"]')
    expect(badge.text()).toBe('Request refused')
    expect(await hintText(badge)).toBe(detail)
  })

  it('shows time and cost, split by role', () => {
    const { wrapper } = mountPage(
      runReport({
        run: runSummary('j1', {
          started_at: '2026-09-30T06:00:00Z',
          finished_at: '2026-09-30T06:54:00Z',
        }),
        method: {
          ...runReport().method,
          cost: {
            usd: 18.52,
            usd_calls: 18.4,
            total_usd: 18.4,
            by_role: { writer: 5.1, web_check: 2.3, subjects: 7.6, judges: 3.4 },
          },
        },
      }),
    )
    expect(wrapper.get('[data-testid="run-articles"]').text()).toMatch(
      / · took 54 min · cost \$18\.40$/,
    )
    const section = wrapper.get('[data-testid="time-cost"]')
    expect(section.text()).toContain('Paid with your own model keys.')
    expect(wrapper.get('[data-testid="took"]').text()).toMatch(
      /^Took54 minStarted \d{2}:\d{2} · finished \d{2}:\d{2}$/,
    )
    expect(wrapper.get('[data-testid="cost"]').text()).toBe('Cost$18.40All model calls in this run')
    const bar = wrapper.get('[role="img"]')
    expect(bar.attributes('aria-label')).toContain('Judges $3.40')
    expect(bar.findAll('span')).toHaveLength(4)
    expect(wrapper.get('[data-testid="cost-parts"]').text()).toContain('Models being tested$7.60')
  })

  it('hides time and cost when the run has neither', () => {
    const { wrapper } = mountPage(runReport())
    expect(wrapper.find('[data-testid="time-cost"]').exists()).toBe(false)
  })

  it('shows only the cost tile without a split', () => {
    const { wrapper } = mountPage(
      runReport({
        method: {
          ...runReport().method,
          cost: { usd: null, usd_calls: 0.5 },
        },
      }),
    )
    expect(wrapper.get('[data-testid="cost"]').text()).toContain('$0.50')
    expect(wrapper.find('[data-testid="took"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="cost-parts"]').exists()).toBe(false)
  })

  it('offers the summary download', async () => {
    const { wrapper, actions } = mountPage(runReport())
    await wrapper.get('[data-testid="download-summary"]').trigger('click')
    expect(actions.downloadSummary).toHaveBeenCalledWith('j1')
    expect(wrapper.find('[data-testid="download-excel"]').exists()).toBe(false)
  })

  it('offers the Excel download with Details on', async () => {
    const details = useDetails()
    details.value = true
    const { wrapper } = mountPage(runReport())
    await wrapper.get('[data-testid="download-excel"]').trigger('click')
    expect(saveRunExport).toHaveBeenCalledWith('ep', 'j1')
    details.value = false
  })

  it('points a build-only run to the method page', () => {
    const base = runReport()
    const { wrapper } = mountPage({ ...base, run: { ...base.run, build_only: true } })
    expect(wrapper.find('[data-testid="build-only"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="download-summary"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="model-row"]').exists()).toBe(false)
  })
})
