import { afterEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, ref, shallowRef, type Component } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { BenchmarkQuestionPage, BenchmarkQuestionQuery, BenchmarkRunReport } from '@/api/types'
import {
  provideRun,
  provideRunReport,
  type RunContext,
} from '@/components/benchmark/report/context'
import type { RunReport } from '@/components/benchmark/report/useRunReport'
import ReportChecks from '@/components/benchmark/report/ReportChecks.vue'
import ReportMethod from '@/components/benchmark/report/ReportMethod.vue'
import ReportQuestions from '@/components/benchmark/report/ReportQuestions.vue'
import {
  GEMINI,
  GPT,
  modelReport,
  OPUS,
  questionDetail,
  questionRow,
  runReport,
} from './reportFixtures'

vi.mock('vue-sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const COUNTS = { all: 30, fixed: 12, either: 10, still: 6, worse: 2 }

function questionPage(query: BenchmarkQuestionQuery): BenchmarkQuestionPage {
  if (query.excluded === 'only') {
    return {
      items: [questionRow('x1', { excluded: true })],
      total: 1,
      counts: { all: 1, fixed: 1, either: 0, still: 0, worse: 0 },
    }
  }
  const offset = query.offset ?? 0
  const total = query.group ? 12 : 30
  const n = Math.max(Math.min(query.limit ?? 25, total - offset), 0)
  return {
    items: Array.from({ length: n }, (_, i) => questionRow(`q${offset + i + 1}`)),
    total,
    counts: COUNTS,
  }
}

function fakeReport() {
  return {
    revision: ref(0),
    loadQuestions: vi.fn(async (_job: string, query: BenchmarkQuestionQuery) =>
      questionPage(query),
    ),
    loadQuestion: vi.fn(async (_job: string, qaId: string, _model: string) => questionDetail(qaId)),
    loadFragments: vi.fn(async () => [
      {
        file_name: 'b.md',
        document_title: 'Article B',
        score: 0.9,
        content: 'Other passage',
        is_source: false,
      },
      {
        file_name: 'a.md',
        document_title: 'Article A',
        score: 0.8,
        content: 'The source passage',
        is_source: true,
      },
    ]),
    overrideVerdict: vi.fn(async () => {}),
    withdrawOverride: vi.fn(async () => {}),
    excludeQuestion: vi.fn(async () => {}),
    restoreQuestion: vi.fn(async () => {}),
  }
}

function setup(component: Component, data: BenchmarkRunReport = runReport()) {
  const report = fakeReport()
  const kind = ref<string | null>(null)
  const dataRef = shallowRef<BenchmarkRunReport | null>(data)
  const ctx: RunContext = {
    jobId: 'job1',
    data: dataRef,
    loading: ref(false),
    error: ref(null),
    running: computed(() => false),
    model: computed(() => OPUS),
    modelReport: computed(() => dataRef.value?.models.find((m) => m.model === OPUS) ?? null),
    selectModel: vi.fn(),
    kind,
    setKind: (k) => (kind.value = k),
    reload: vi.fn(async () => {}),
  }
  const Host = defineComponent({
    setup() {
      provideRunReport(report as unknown as RunReport)
      provideRun(ctx)
      return () => h(component, { slug: 'ep', jobId: 'job1', modelId: OPUS })
    },
  })
  const wrapper = mount(Host, { attachTo: document.body })
  mounted.push(wrapper)
  return { wrapper, report, ctx }
}

const mounted: VueWrapper[] = []
afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  document.body.innerHTML = ''
  vi.useRealTimers()
})

function rows(wrapper: VueWrapper) {
  return wrapper.findAll('[data-testid="question-row"]')
}

function inBody(selector: string): HTMLElement {
  const el = document.body.querySelector<HTMLElement>(selector)
  if (!el) throw new Error(`${selector} not found`)
  return el
}

function lastQuery(report: ReturnType<typeof fakeReport>, excluded = 'include') {
  const calls = report.loadQuestions.mock.calls.filter(([, q]) => q.excluded === excluded)
  return calls[calls.length - 1]![1]
}

describe('ReportQuestions', () => {
  it('shows server counts, an Excluded chip and the first page', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    expect(wrapper.get('[data-testid="group-all"]').text()).toBe('All questions · 30')
    expect(wrapper.get('[data-testid="group-fixed"]').text()).toBe('Your data fixed it · 12')
    expect(wrapper.get('[data-testid="group-worse"]').text()).toBe('Worse with your data · 2')
    expect(wrapper.get('[data-testid="group-excluded"]').text()).toBe('Excluded · 1')
    expect(rows(wrapper)).toHaveLength(25)
    expect(wrapper.get('[data-testid="question-range"]').text()).toBe(
      'Showing 1–25 of 30 questions',
    )
    expect(rows(wrapper)[0]!.text()).toContain('Names · Article A')
    expect(lastQuery(report)).toMatchObject({
      model: OPUS,
      excluded: 'include',
      limit: 25,
      offset: 0,
    })
    expect(lastQuery(report, 'only')).toMatchObject({ limit: 1 })
  })

  it('hides the Excluded chip when nothing is excluded', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    report.loadQuestions.mockImplementation(async (_job, query) =>
      query.excluded === 'only' ? { items: [], total: 0, counts: COUNTS } : questionPage(query),
    )
    report.revision.value += 1
    await flushPromises()
    expect(wrapper.find('[data-testid="group-excluded"]').exists()).toBe(false)
  })

  it('sends group and kind to the server', async () => {
    const { wrapper, report, ctx } = setup(ReportQuestions)
    await flushPromises()
    await wrapper.get('[data-testid="group-fixed"]').trigger('click')
    await flushPromises()
    expect(lastQuery(report)).toMatchObject({ group: 'fixed', offset: 0 })
    expect(rows(wrapper)).toHaveLength(12)

    ctx.kind.value = 'mcq'
    await flushPromises()
    expect(lastQuery(report)).toMatchObject({ group: 'fixed', generator: 'mcq' })
    await wrapper.get('[data-testid="kind-chip"]').trigger('click')
    expect(ctx.kind.value).toBeNull()
    await flushPromises()
    expect(lastQuery(report)).not.toHaveProperty('q')
    expect(wrapper.find('input[type="search"]').exists()).toBe(false)
  })

  it('lists excluded questions with a badge', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    await wrapper.get('[data-testid="group-excluded"]').trigger('click')
    await flushPromises()
    expect(lastQuery(report, 'only')).toMatchObject({ limit: 25 })
    expect(rows(wrapper)).toHaveLength(1)
    expect(rows(wrapper)[0]!.get('[data-testid="excluded-badge"]').text()).toBe('Excluded')
    // Chip counts stay those with excluded questions included.
    expect(wrapper.get('[data-testid="group-all"]').text()).toBe('All questions · 30')
  })

  it('pages on the server', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    await wrapper.get('[data-testid="next-page"]').trigger('click')
    await flushPromises()
    expect(lastQuery(report)).toMatchObject({ offset: 25 })
    expect(rows(wrapper)).toHaveLength(5)
    expect(wrapper.get('[data-testid="question-range"]').text()).toBe(
      'Showing 26–30 of 30 questions',
    )
  })

  it('loads a question’s detail when expanded, one at a time', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    const first = rows(wrapper)[0]!.get('button')
    await first.trigger('click')
    await flushPromises()
    expect(report.loadQuestion).toHaveBeenCalledWith('job1', 'q1', OPUS)
    expect(first.attributes('aria-expanded')).toBe('true')
    const detail = wrapper.get('[data-testid="question-detail"]')
    expect(detail.text()).toContain('Gold q1')
    expect(detail.get('[data-testid="retrieval"]').text()).toBe(
      'Given 3 passages from your archive; the right one ranked 2nd',
    )
    expect(detail.text()).toContain('GPT-5.1')
    expect(detail.text()).toContain('Gemini 3.1 Pro')
    expect(detail.text()).toContain('All judges agreed.')
    expect(detail.text()).toContain('Held when challenged')
    expect(detail.text()).toContain('1 of 3')
    expect(detail.text()).toContain('3 of 4')

    await rows(wrapper)[1]!.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="question-detail"]')).toHaveLength(1)
    expect(first.attributes('aria-expanded')).toBe('false')
  })

  it('loads the passages sent with a question', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    await rows(wrapper)[0]!.get('button').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="show-source"]').trigger('click')
    await flushPromises()
    expect(report.loadFragments).toHaveBeenCalledWith('job1', 'q1', OPUS)
    const body = inBody('[data-testid="excerpts"]').textContent ?? ''
    expect(body).toContain('From “Article A”')
    expect(body).toContain('The source passage')
    expect(body).toContain('Right passage')
  })

  it('changes a verdict through the arm’s result id, then refetches', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    await rows(wrapper)[0]!.get('button').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="change-verdict"]').trigger('click')
    await flushPromises()
    inBody('#override-verdict-abstain').click()
    await flushPromises()
    inBody('[data-testid="save-override"]').click()
    await flushPromises()
    expect(report.overrideVerdict).toHaveBeenCalledWith('job1', 'q1-with', 'abstain', '')

    const pages = report.loadQuestions.mock.calls.length
    const details = report.loadQuestion.mock.calls.length
    report.revision.value += 1
    await flushPromises()
    expect(report.loadQuestions.mock.calls.length).toBe(pages + 2)
    expect(report.loadQuestion.mock.calls.length).toBe(details + 1)
  })

  it('withdraws an existing override', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    const d = questionDetail('q1')
    d.arms.with!.override = {
      id: 'ov1',
      verdict: 'abstain',
      reasoning: '',
      created_at: '2026-09-30T07:00:00Z',
    }
    report.loadQuestion.mockResolvedValue(d)
    await flushPromises()
    await rows(wrapper)[0]!.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="question-detail"]').text()).toContain(
      'Verdict changed by you',
    )
    await wrapper.get('[data-testid="change-verdict"]').trigger('click')
    await flushPromises()
    inBody('[data-testid="withdraw-override"]').click()
    await flushPromises()
    expect(report.withdrawOverride).toHaveBeenCalledWith('job1', 'ov1')
  })

  it('removes a question with a reason, optionally for future runs', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    await flushPromises()
    await rows(wrapper)[0]!.get('button').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="remove-question"]').trigger('click')
    await flushPromises()
    const note = inBody('#remove-note') as HTMLTextAreaElement
    note.value = 'Ambiguous'
    note.dispatchEvent(new Event('input'))
    inBody('#remove-retire').click()
    await flushPromises()
    inBody('[data-testid="confirm-remove"]').click()
    await flushPromises()
    expect(report.excludeQuestion).toHaveBeenCalledWith('job1', 'q1', 'Ambiguous', true)
  })

  it('restores an excluded question', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    report.loadQuestion.mockResolvedValue(
      questionDetail('q1', {
        question: questionRow('q1', { excluded: true }),
        exclusion: { reason: '', created_at: '2026-09-30T07:00:00Z' },
      }),
    )
    await flushPromises()
    await rows(wrapper)[0]!.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="remove-question"]').exists()).toBe(false)
    await wrapper.get('[data-testid="restore-question"]').trigger('click')
    await flushPromises()
    expect(report.restoreQuestion).toHaveBeenCalledWith('job1', 'q1')
  })

  it('says when no questions match', async () => {
    const { wrapper, report } = setup(ReportQuestions)
    report.loadQuestions.mockResolvedValue({
      items: [],
      total: 0,
      counts: { all: 0, fixed: 0, either: 0, still: 0, worse: 0 },
    })
    report.revision.value += 1
    await flushPromises()
    expect(wrapper.find('[data-testid="questions-empty"]').exists()).toBe(true)
  })
})

describe('ReportChecks', () => {
  it('shows a dash for every check it cannot compute', () => {
    const { wrapper } = setup(ReportChecks)
    const values = wrapper.findAll('[data-testid="check-value"]').map((v) => v.text())
    expect(values).toEqual(['—', '—', '—', '—'])
    expect(wrapper.find('[data-testid="check-trick"] button').exists()).toBe(false)
  })

  it('reads the server’s checks', () => {
    const data = runReport({
      models: [
        modelReport(OPUS, {
          checks: {
            challenged: 40,
            denial_limit: 3,
            held_by_round: [0.9, 0.8, 0.75],
            kept_right: 0.75,
            repeated: 30,
            same_answer: 0.6,
            by_temperature: [
              { t: 0.9, accuracy: 0.5 },
              { t: 0.3, accuracy: 0.7 },
            ],
            trick_asked: 5,
            trick_answered: 2,
            trick_alone_asked: 5,
            trick_alone_answered: 4,
            searched: 100,
            search_found: 0.82,
            missed: 18,
            answers: 200,
            judges_agreed: 180,
            agreement: 0.9,
          },
        }),
      ],
    })
    const { wrapper } = setup(ReportChecks, data)
    const values = wrapper.findAll('[data-testid="check-value"]').map((v) => v.text())
    expect(values).toEqual(['75%', '60%', '2 of 5', '82%'])
    expect(wrapper.get('[data-testid="check-challenged"]').text()).toContain('up to 3 times')
    expect(wrapper.get('[data-testid="check-trick"] button').attributes('aria-label')).toBe(
      'On its own it answered 4 of 5.',
    )
  })
})

describe('ReportMethod', () => {
  it('shows a dash for every figure and setting it does not have', () => {
    const data = runReport({
      run: { ...runReport().run, articles: null },
      funnel: { written: null, removed: {}, removed_total: null, asked: 0, trick: 0 },
      judges: [],
    })
    const { wrapper } = setup(ReportMethod, data)
    for (const step of ['written', 'removed', 'asked']) {
      expect(wrapper.get(`[data-testid="funnel-${step}"] p`).text()).toBe('—')
    }
    const settings = wrapper.findAll('dd').map((d) => d.text())
    expect(settings).toHaveLength(8)
    expect(settings.filter((s) => s === '—')).toHaveLength(7)
    expect(wrapper.get('[data-testid="setting-leaves"] dd').text()).not.toBe('—')
  })

  it('shows the funnel and the method of a run', () => {
    const data = runReport({
      funnel: {
        written: 120,
        removed: { grounding: 12, duplicate: 8 },
        removed_total: 20,
        asked: 100,
        trick: 5,
      },
      method: {
        articles_from: '2026-09-29T06:00:00Z',
        articles_to: '2026-09-30T06:00:00Z',
        generator_model: 'anthropic/claude-opus-5.5',
        kinds: ['mcq', 'qa', 'unanswerable_property'],
        trick: 5,
        context_docs: 5,
        judges: [GPT, GEMINI],
        profile: 'demosyft',
        next_run_at: null,
      },
    })
    const { wrapper } = setup(ReportMethod, data)
    expect(wrapper.get('[data-testid="funnel-written"] p').text()).toBe('120')
    expect(wrapper.get('[data-testid="funnel-removed"] p').text()).toBe('20')
    expect(wrapper.get('[data-testid="funnel-removed"] button').attributes('aria-label')).toBe(
      'Not supported by the article: 12, Duplicate: 8.',
    )
    expect(wrapper.get('[data-testid="funnel-asked"] p').text()).toBe('100')
    const text = (key: string) => wrapper.get(`[data-testid="setting-${key}"] dd`).text()
    expect(text('articles')).toMatch(/^9 articles published \d{1,2} Sep \d{2}:\d{2} to /)
    expect(text('writtenBy')).toBe('Claude Opus 5.5, running inside your Syft Space')
    expect(text('kinds')).toBe('2 kinds, plus 5 trick questions with no answer')
    expect(text('asked')).toContain('up to 5 passages')
    expect(text('judges')).toBe(
      'GPT-5.1, Gemini 3.1 Pro. A judge never grades a model from its own company.',
    )
    expect(text('profile')).toBe('demosyft, recorded with every run so results stay comparable')
    expect(text('next')).toBe('—')
  })
})
