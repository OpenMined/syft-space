import { describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, ref, shallowRef } from 'vue'
import { mount } from '@vue/test-utils'
import type { BenchmarkRunReport } from '@/api/types'
import RunMethodPage from '@/components/benchmark/report/RunMethodPage.vue'
import { provideRun } from '@/components/benchmark/report/context'
import { GEMINI, GPT, OPUS, QWEN, modelReport, runReport } from './reportFixtures'

function mountPage(report: BenchmarkRunReport) {
  const Host = defineComponent({
    setup() {
      provideRun({
        jobId: 'j1',
        data: shallowRef(report),
        loading: ref(false),
        error: ref(null),
        running: computed(() => false),
        model: computed(() => null),
        modelReport: computed(() => null),
        reload: vi.fn(),
      })
      return () => h(RunMethodPage)
    },
  })
  return mount(Host)
}

function full(): BenchmarkRunReport {
  const base = runReport()
  return runReport({
    funnel: { written: 1000, removed: {}, removed_total: 0, asked: 100, trick: 4 },
    judges: [GPT, GEMINI],
    method: {
      ...base.method,
      articles_from: '2026-09-29T06:00:00Z',
      articles_to: '2026-09-30T06:00:00Z',
      generator_model: 'anthropic/claude-opus-5.5',
      kinds: ['temporal_masking', 'named_entity_masking', 'mcq', 'unanswerable_property'],
      trick: 4,
      judges: [GPT, GEMINI],
      profile: 'demosyft',
      denial_rounds: 3,
      repeats: { trials: 2, temperatures: [0.3, 0.9] },
    },
  })
}

function setting(wrapper: ReturnType<typeof mount>, key: string): string {
  return wrapper.get(`[data-testid="setting-${key}"] dd`).text()
}

describe('RunMethodPage', () => {
  it('fills the settings table from the run', () => {
    const wrapper = mountPage(full())
    expect(wrapper.get('h1').text()).toBe('How this run was tested')
    expect(wrapper.text()).toContain(
      'The settings used in the run of 30 Sep 2026. Another run can use different settings.',
    )
    expect(setting(wrapper, 'articles')).toMatch(
      /^9 articles published 29 Sep 2026 \d{2}:\d{2} to 30 Sep 2026 \d{2}:\d{2}$/,
    )
    expect(setting(wrapper, 'written')).toBe('1,000, by Claude Opus 5.5 inside your Syft Space')
    expect(setting(wrapper, 'removed')).toBe('—')
    expect(setting(wrapper, 'asked')).toBe('100, plus 4 trick questions')
    expect(setting(wrapper, 'models')).toBe('Claude Opus 4.8, Qwen 3.8 27B')
    expect(setting(wrapper, 'judges')).toBe('GPT-5.1, Gemini 3.1 Pro')
    expect(setting(wrapper, 'rounds')).toBe('Up to 3 per right answer')
    expect(setting(wrapper, 'repeats')).toBe('4 per question, at a steady and a looser setting')
    expect(setting(wrapper, 'profile')).toBe('demosyft')
    expect(wrapper.get('[data-testid="checks-text"]').text()).toBe(
      'Right answers were challenged with “Are you sure?” up to 3 times. Every question was asked again 4 more times. Trick questions with no answer in your reporting tested whether a model would refuse rather than hallucinate.',
    )
  })

  it('shows dashes for settings the run did not record', () => {
    const wrapper = mountPage(
      runReport({
        funnel: { written: null, removed: {}, removed_total: null, asked: 100, trick: 0 },
      }),
    )
    expect(setting(wrapper, 'written')).toBe('—')
    expect(setting(wrapper, 'asked')).toBe('100')
    expect(setting(wrapper, 'rounds')).toBe('—')
    expect(setting(wrapper, 'repeats')).toBe('—')
    expect(setting(wrapper, 'profile')).toBe('—')
    expect(wrapper.get('[data-testid="checks-text"]').text()).toBe(
      'Trick questions with no answer in your reporting tested whether a model would refuse rather than hallucinate.',
    )
  })

  it('states the web check counts only when they are known', () => {
    expect(mountPage(full()).get('[data-testid="web-check"]').text()).not.toContain('Of 1,000')
    const known = full()
    known.funnel.removed = { web_answerable: 900 }
    expect(mountPage(known).get('[data-testid="web-check"]').text()).toContain(
      'Of 1,000 questions written, 900 were removed and 100 were asked.',
    )
  })

  it('lists kinds in the server order with the asked counts, trick included', () => {
    const report = full()
    const kind = modelReport(OPUS).kinds[0]!
    report.models = [
      modelReport(OPUS, {
        kinds: [
          { ...kind, generator: 'named_entity_masking', asked: 12 },
          { ...kind, generator: 'temporal_masking', asked: 30 },
        ],
      }),
      modelReport(QWEN),
    ]
    const rows = mountPage(report).findAll('[data-testid="kind-row"]')
    expect(rows.map((r) => r.findAll('th, td').map((c) => c.text()))).toEqual([
      ['Dates', 'Fill in a missing date.', '30'],
      ['Names', 'Fill in a missing name in a sentence from your article.', '12'],
      ['Multiple choice', 'Pick the right answer from four.', '0'],
      [
        'Trick questions',
        'Ask for a detail your reporting does not contain. The right response is “I don’t know”.',
        '4',
      ],
    ])
  })

  it('shows the grading words', () => {
    const text = mountPage(full()).text()
    expect(text).toContain('Right')
    expect(text).toContain('Didn’t know')
    expect(text).toContain('Hallucinated')
  })
})
