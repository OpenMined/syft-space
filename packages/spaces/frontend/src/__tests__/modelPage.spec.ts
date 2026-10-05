import { describe, expect, it } from 'vitest'
import { computed, defineComponent, h, ref } from 'vue'
import { mount, RouterLinkStub } from '@vue/test-utils'
import type { BenchmarkRunReport } from '@/api/types'
import ModelPage from '@/components/benchmark/report/ModelPage.vue'
import { provideRun, type RunContext } from '@/components/benchmark/report/context'
import { modelReport, OPUS, runReport } from './reportFixtures'

function mountPage(data: BenchmarkRunReport, model: string) {
  const dataRef = ref(data)
  const run = {
    jobId: 'j1',
    data: dataRef,
    loading: ref(false),
    error: ref(null),
    running: computed(() => false),
    model: computed(() => model),
    modelReport: computed(() => dataRef.value.models.find((m) => m.model === model) ?? null),
    reload: async () => {},
  } as unknown as RunContext
  const Host = defineComponent({
    setup() {
      provideRun(run)
      return () => h(ModelPage)
    },
  })
  return mount(Host, { global: { stubs: { RouterLink: RouterLinkStub } } })
}

describe('ModelPage', () => {
  it('shows the title, subtitle and the three stats', () => {
    const wrapper = mountPage(runReport(), OPUS)
    expect(wrapper.get('h1').text()).toBe('Claude Opus 4.8')
    expect(wrapper.get('[data-testid="model-subtitle"]').text()).toBe(
      'Anthropic · asked the same 100 questions twice: on its own, and with your data',
    )
    const stats = wrapper.get('[data-testid="model-stats"]').text()
    expect(stats).toContain('80 of 100')
    expect(stats).toContain('right with your data')
    expect(stats).toContain('30 of 100')
    expect(stats).toContain('right on its own')
    expect(stats).toContain('+50 points')
    expect(stats).toContain('added by your data')
  })

  it('stacks the answers of both arms and says how hallucinations changed', () => {
    const wrapper = mountPage(runReport(), OPUS)
    expect(wrapper.get('[data-testid="answered-with"]').text()).toMatch(
      /With your data\s*80\s*right\s*12\s*didn’t know\s*8\s*hallucinated/,
    )
    expect(wrapper.get('[data-testid="answered-alone"]').text()).toMatch(
      /On its own\s*30\s*right\s*45\s*didn’t know\s*25\s*hallucinated/,
    )
    expect(wrapper.get('[data-testid="answered-foot"]').text()).toBe(
      'Hallucinations fell from 25 to 8 when the model had your data.',
    )
  })

  it('says "went" when hallucinations did not fall', () => {
    const base = modelReport(OPUS)
    const report = runReport({
      models: [
        modelReport(OPUS, {
          tally: { alone: { ...base.tally.alone, hallucinate: 4 }, with: base.tally.with },
        }),
      ],
    })
    expect(mountPage(report, OPUS).get('[data-testid="answered-foot"]').text()).toBe(
      'Hallucinations went from 4 to 8 when the model had your data.',
    )
  })

  it('lists kinds in the order the server returns them, without sorting by lift', () => {
    const base = modelReport(OPUS)
    const [names, dates] = base.kinds
    const report = runReport({
      models: [
        modelReport(OPUS, {
          kinds: [
            { ...names!, lift: 10 },
            { ...dates!, lift: 70 },
          ],
        }),
      ],
    })
    const wrapper = mountPage(report, OPUS)
    expect(wrapper.text()).toContain('Right answers by kind of question.')
    expect(wrapper.text()).not.toContain('biggest difference first')
    const rows = wrapper.findAll('[data-testid="kind-row"]')
    expect(rows.map((r) => r.find('td').text())).toEqual(['Names', 'Dates'])
    const cells = rows[0]!.findAll('td').map((td) => td.text())
    expect(cells).toEqual(['Names', '10', '10%', '90%', '+10'])
    expect(rows[1]!.get('[data-testid="kind-bar"]').attributes('style')).toContain('width: 70%')
  })

  it('shows a dash and no bar for a kind without a lift', () => {
    const [names] = modelReport(OPUS).kinds
    const report = runReport({
      models: [
        modelReport(OPUS, {
          kinds: [{ ...names!, rate_alone: null, rate_with: null, lift: null }],
        }),
      ],
    })
    const row = mountPage(report, OPUS).get('[data-testid="kind-row"]')
    expect(row.findAll('td').map((td) => td.text())).toEqual(['Names', '10', '—', '—', '—'])
    expect(row.find('[data-testid="kind-bar"]').exists()).toBe(false)
  })

  it('links to the questions and the checks of this model', () => {
    const wrapper = mountPage(runReport(), OPUS)
    const links = wrapper.findAllComponents(RouterLinkStub)
    expect(links.map((l) => l.props('to'))).toEqual([
      { query: { tab: 'results', job: 'j1', model: OPUS, screen: 'questions' } },
      { query: { tab: 'results', job: 'j1', model: OPUS, screen: 'checks' } },
    ])
    expect(wrapper.get('[data-testid="link-questions"]').text()).toContain(
      'All 100 questions, both of the model’s answers, and what each judge decided and why',
    )
    expect(wrapper.get('[data-testid="link-checks"]').text()).toContain('Reliability checks')
  })

  it('shows a short empty state for a model not in the run', () => {
    const wrapper = mountPage(runReport(), 'nobody/unknown')
    expect(wrapper.find('[data-testid="model-missing"]').exists()).toBe(true)
    expect(wrapper.find('h1').exists()).toBe(false)
  })
})
