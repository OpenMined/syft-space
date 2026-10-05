import { describe, expect, it } from 'vitest'
import { computed, defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import type { BenchmarkRunChecks, BenchmarkRunReport } from '@/api/types'
import ChecksPage from '@/components/benchmark/report/ChecksPage.vue'
import { provideRun, type RunContext } from '@/components/benchmark/report/context'
import { modelReport, OPUS, runReport } from './reportFixtures'

const MEASURED: BenchmarkRunChecks = {
  challenged: 80,
  denial_limit: 3,
  held_by_round: [0.93, 0.88, 0.875],
  kept_right: 0.875,
  repeated: 100,
  same_answer: 0.8,
  by_temperature: [
    { t: 0.9, accuracy: 0.75 },
    { t: 0.3, accuracy: 0.79 },
  ],
  trick_asked: 4,
  trick_answered: 0,
  trick_alone_asked: null,
  trick_alone_answered: null,
  searched: 100,
  search_found: 0.96,
  missed: 4,
  answers: 200,
  judges_agreed: 185,
  agreement: 0.925,
}

function report(checks: Partial<BenchmarkRunChecks>, extra: Partial<BenchmarkRunReport> = {}) {
  const base = runReport()
  return runReport({
    models: [modelReport(OPUS, { checks: { ...MEASURED, ...checks } })],
    method: { ...base.method, repeats: { trials: 2, temperatures: [0.3, 0.9] } },
    ...extra,
  })
}

function mountPage(data: BenchmarkRunReport, model = OPUS) {
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
      return () => h(ChecksPage)
    },
  })
  return mount(Host)
}

function lines(wrapper: ReturnType<typeof mountPage>, key: string) {
  return wrapper
    .get(`[data-testid="check-${key}"]`)
    .findAll('[data-testid="check-line"]')
    .map((l) =>
      [...l.element.children]
        .map((c) => c.textContent?.trim())
        .filter(Boolean)
        .join(' '),
    )
}

function reading(wrapper: ReturnType<typeof mountPage>, key: string) {
  return wrapper.get(`[data-testid="check-${key}"] [data-testid="check-reading"]`).text()
}

describe('ChecksPage', () => {
  it('shows the title and five checks with their readings', () => {
    const wrapper = mountPage(report({}))
    expect(wrapper.get('h1').text()).toBe('Reliability checks')
    expect(wrapper.text()).toContain('Extra tests on Claude Opus 4.8’s answers with your data.')

    const held = wrapper.get('[data-testid="check-challenged"]')
    expect(held.text()).toContain('up to 3 times. Share still giving the right answer:')
    expect(lines(wrapper, 'challenged')).toEqual([
      'First answer 100%',
      'After round 1 93%',
      'After round 2 88%',
      'After round 3 88%',
    ])
    expect(reading(wrapper, 'challenged')).toBe(
      'Gave up a right answer at some point on 13% of questions.',
    )

    expect(wrapper.get('[data-testid="check-repeated"]').text()).toContain(
      'Each question was asked 4 more times, twice at a steady setting and twice at a looser one.',
    )
    expect(lines(wrapper, 'repeated')).toEqual(['Steady 79%', 'Looser 75%'])
    expect(reading(wrapper, 'repeated')).toBe(
      'Gave the same answer every time on 80% of questions.',
    )

    expect(wrapper.get('[data-testid="check-trick"]').text()).toContain(
      '4 trick questions asked for details your reporting does not contain.',
    )
    expect(wrapper.findAll('[data-testid="check-square"]')).toHaveLength(4)
    expect(reading(wrapper, 'trick')).toBe(
      'Refused all 4. It hallucinated an answer to none of them.',
    )

    expect(lines(wrapper, 'search')).toEqual(['Found 96%'])
    expect(reading(wrapper, 'search')).toBe(
      'On 4 questions the source paragraph was not among the excerpts.',
    )

    expect(wrapper.get('[data-testid="check-judges"]').text()).toContain(
      'Judge 1 (GPT-5.1) and Judge 2 (Gemini 3.1 Pro) graded every answer.',
    )
    expect(lines(wrapper, 'judges')).toEqual(['Agreed 93%'])
    expect(reading(wrapper, 'judges')).toBe('They disagreed on 15 of 200 answers.')
  })

  it('marks the trick questions the model answered', () => {
    const wrapper = mountPage(report({ trick_asked: 4, trick_answered: 1 }))
    const squares = wrapper.findAll('[data-testid="check-square"]')
    expect(squares.map((s) => s.attributes('data-bad'))).toEqual([
      'true',
      'false',
      'false',
      'false',
    ])
    expect(reading(wrapper, 'trick')).toBe('Hallucinated an answer to 1 of 4.')
  })

  it('shows dashes and no bars for unmeasured checks, never NaN', () => {
    const base = runReport()
    const wrapper = mountPage(
      runReport({ models: [modelReport(OPUS)], method: { ...base.method, repeats: null } }),
    )
    expect(wrapper.text()).not.toContain('NaN')
    expect(lines(wrapper, 'challenged')).toEqual([])
    expect(reading(wrapper, 'challenged')).toBe(
      'Gave up a right answer at some point on — of questions.',
    )
    expect(wrapper.get('[data-testid="check-repeated"]').text()).toContain(
      'Each question was asked — more times.',
    )
    expect(lines(wrapper, 'repeated')).toEqual(['Steady —', 'Looser —'])
    expect(reading(wrapper, 'repeated')).toBe('Gave the same answer every time on — of questions.')
    expect(wrapper.findAll('[data-testid="check-square"]')).toHaveLength(0)
    expect(reading(wrapper, 'trick')).toBe('—')
    expect(lines(wrapper, 'search')).toEqual(['Found —'])
    expect(reading(wrapper, 'search')).toBe('—')
    expect(reading(wrapper, 'judges')).toBe('—')
    const bars = wrapper.findAll('[data-testid="check-line"] .bg-chart-5')
    expect(bars).toHaveLength(0)
  })

  it('words the repeats from trials per temperature', () => {
    const base = runReport()
    const text = (repeats: { trials: number; temperatures: number[] }) =>
      mountPage(report({}, { method: { ...base.method, repeats } }))
        .get('[data-testid="check-repeated"]')
        .text()
    expect(text({ trials: 3, temperatures: [0.3, 0.9] })).toContain(
      'Each question was asked 6 more times, three times at a steady setting and three times at a looser one.',
    )
    expect(text({ trials: 5, temperatures: [0.3, 0.9] })).toContain(
      'asked 10 more times, 5 times at a steady setting and 5 times at a looser one.',
    )
    expect(text({ trials: 4, temperatures: [0.3] })).toContain(
      'Each question was asked 4 more times at the same setting.',
    )
    expect(text({ trials: 2, temperatures: [0.1, 0.5, 0.9] })).toContain(
      'Each question was asked 6 more times, twice at each of 3 settings.',
    )
  })

  it('shows a short empty state for a model not in the run', () => {
    const wrapper = mountPage(report({}), 'nobody/unknown')
    expect(wrapper.find('[data-testid="checks-missing"]').exists()).toBe(true)
  })
})
