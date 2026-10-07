import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, ref, shallowRef } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { BenchmarkQuestionPage, BenchmarkQuestionQuery } from '@/api/types'
import QuestionsPage from '@/components/benchmark/report/QuestionsPage.vue'
import {
  provideRun,
  provideRunReport,
  type RunContext,
} from '@/components/benchmark/report/context'
import type { RunReport } from '@/components/benchmark/report/useRunReport'
import { Select } from '@/components/ui/select'
import { GEMINI, GPT, OPUS, questionDetail, questionRow, runReport } from './reportFixtures'

const KINDS = ['temporal_masking', 'named_entity_masking', 'unanswerable_property', 'mcq']

function page(items = [questionRow('q1'), questionRow('q2', { n: 2 })], total = items.length) {
  return {
    items,
    total,
    counts: { all: 100, fixed: 51, either: 29, still: 19, worse: 1 },
  } satisfies BenchmarkQuestionPage
}

function fakeReport(list: BenchmarkQuestionPage = page()) {
  return {
    revision: ref(0),
    loadQuestions: vi.fn(async (_job: string, _query: BenchmarkQuestionQuery) => list),
    loadQuestion: vi.fn(async (_job: string, qaId: string) =>
      questionDetail(qaId, {
        question: questionRow(qaId, { generator: 'multihop_synthesis' }),
        judges: [
          {
            model: GEMINI,
            primary: false,
            alone: 'correct',
            with: 'correct',
            alone_reasoning: null,
            with_reasoning: 'Covers both parts.',
          },
          {
            model: GPT,
            primary: true,
            alone: 'hallucinate',
            with: 'correct',
            alone_reasoning: 'The figure is not in the article.',
            with_reasoning: 'Matches the article.',
          },
        ],
      }),
    ),
    loadFragments: vi.fn(async () => [
      {
        file_name: 'a.md',
        document_title: 'Article A',
        score: 0.9,
        content: 'First passage text.',
        is_source: true,
      },
      { file_name: 'b.md', document_title: '', score: 0.5, content: 'Second.', is_source: false },
    ]),
  }
}

function fakeRun() {
  const data = shallowRef(runReport({ method: { ...runReport().method, kinds: KINDS } }))
  return {
    jobId: 'j1',
    data,
    loading: ref(false),
    error: ref<string | null>(null),
    running: computed(() => false),
    model: computed(() => OPUS),
    modelReport: computed(() => data.value.models.find((m) => m.model === OPUS) ?? null),
    reload: vi.fn(async () => {}),
  } satisfies RunContext
}

let wrapper: VueWrapper | null = null

async function mountPage(report = fakeReport()) {
  const run = fakeRun()
  const Host = defineComponent({
    setup() {
      provideRunReport(report as unknown as RunReport)
      provideRun(run)
      return () => h(QuestionsPage)
    },
  })
  wrapper = mount(Host, { attachTo: document.body })
  await flushPromises()
  return { wrapper, report }
}

function lastQuery(report: ReturnType<typeof fakeReport>): BenchmarkQuestionQuery {
  const calls = report.loadQuestions.mock.calls
  return calls[calls.length - 1]![1]
}

const squash = (s: string) => s.replace(/\s+/g, ' ').trim()

/** Text nodes joined by spaces, so adjacent cells stay apart. */
function words(w: { element: Element }): string {
  const walker = document.createTreeWalker(w.element, NodeFilter.SHOW_TEXT)
  const parts: string[] = []
  while (walker.nextNode()) parts.push(walker.currentNode.textContent ?? '')
  return squash(
    parts
      .map((t) => t.trim())
      .filter(Boolean)
      .join(' '),
  )
}

beforeEach(() => {
  document.body.innerHTML = ''
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
})

describe('QuestionsPage', () => {
  it('names the model, the question count and every judge', async () => {
    const { wrapper } = await mountPage()
    expect(wrapper.get('h1').text()).toBe('Every question and answer')
    expect(wrapper.get('[data-testid="questions-subtitle"]').text()).toBe(
      'Claude Opus 4.8 · 100 questions · graded by Judge 1 (GPT-5.1) and Judge 2 (Gemini 3.1 Pro)',
    )
  })

  it('shows group chips with server counts and filters by group', async () => {
    const { wrapper, report } = await mountPage()
    expect(lastQuery(report)).toEqual({
      model: OPUS,
      group: undefined,
      generator: undefined,
      q: undefined,
      excluded: 'hide',
      limit: 25,
      offset: 0,
    })
    const chips = wrapper.findAll('[role="group"] button').map((b) => squash(b.text()))
    expect(chips).toEqual([
      'All questions · 100',
      'Your data fixed it · 51',
      'Right either way · 29',
      'Still wrong · 19',
      'Worse with your data · 1',
    ])
    await wrapper.get('[data-testid="group-still"]').trigger('click')
    await flushPromises()
    expect(lastQuery(report).group).toBe('still')
    expect(wrapper.get('[data-testid="group-still"]').attributes('aria-pressed')).toBe('true')
  })

  it('lists kinds in registry order without trick questions and filters by kind', async () => {
    const { wrapper, report } = await mountPage()
    await wrapper.get('[data-testid="kind-select"]').trigger('keydown', { key: 'ArrowDown' })
    await flushPromises()
    const options = [...document.body.querySelectorAll('[role="option"]')].map((o) =>
      squash(o.textContent ?? ''),
    )
    expect(options).toEqual(['All kinds', 'Dates', 'Names', 'Multiple choice'])

    wrapper.findComponent(Select).vm.$emit('update:modelValue', 'mcq')
    await flushPromises()
    expect(lastQuery(report).generator).toBe('mcq')
  })

  it('debounces the search and sends it as q', async () => {
    vi.useFakeTimers()
    const { wrapper, report } = await mountPage()
    const calls = report.loadQuestions.mock.calls.length
    await wrapper.get('[data-testid="questions-search"]').setValue('  Kharg ')
    expect(report.loadQuestions.mock.calls.length).toBe(calls)
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(lastQuery(report).q).toBe('Kharg')
  })

  it('pages by 25 and resets the page and open row when a filter changes', async () => {
    const items = Array.from({ length: 25 }, (_, i) => questionRow(`q${i}`, { n: i + 1 }))
    const { wrapper, report } = await mountPage(fakeReport(page(items, 60)))
    expect(squash(wrapper.get('[data-testid="question-range"]').text())).toBe(
      'Showing 1–25 of 60 questions',
    )
    expect(wrapper.get('[data-testid="prev-page"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="next-page"]').trigger('click')
    await flushPromises()
    expect(lastQuery(report).offset).toBe(25)
    expect(squash(wrapper.get('[data-testid="question-range"]').text())).toBe(
      'Showing 26–50 of 60 questions',
    )

    await wrapper.findAll('[data-testid="question-row"] > button')[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="question-detail"]').exists()).toBe(true)

    await wrapper.get('[data-testid="group-fixed"]').trigger('click')
    await flushPromises()
    expect(lastQuery(report)).toMatchObject({ group: 'fixed', offset: 0 })
    expect(wrapper.find('[data-testid="question-detail"]').exists()).toBe(false)
  })

  it('shows the empty state', async () => {
    const { wrapper } = await mountPage(fakeReport(page([], 0)))
    expect(wrapper.get('[data-testid="questions-empty"]').text()).toBe(
      'No questions match these filters. Clear a filter or the search to see more.',
    )
    expect(squash(wrapper.get('[data-testid="question-range"]').text())).toBe(
      'Showing 0–0 of 0 questions',
    )
  })

  it('renders rows and opens one at a time with the full detail', async () => {
    const { wrapper, report } = await mountPage()
    const rows = wrapper.findAll('[data-testid="question-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('Question q1')
    expect(rows[0]!.text()).toContain('Names · Article A')
    expect(rows[0]!.get('[data-testid="verdict-closed"]').text()).toBe('Didn’t know')
    expect(rows[0]!.get('[data-testid="verdict-ctx"]').text()).toBe('Right')

    const first = rows[0]!.get('button')
    await first.trigger('click')
    await flushPromises()
    expect(first.attributes('aria-expanded')).toBe('true')
    expect(report.loadQuestion).toHaveBeenCalledWith('j1', 'q1', OPUS)
    expect(report.loadFragments).toHaveBeenCalledWith('j1', 'q1', OPUS)

    const detail = wrapper.get('[data-testid="question-detail"]')
    expect(words(detail)).toContain('Correct answer, from “Article A” Gold q1.')
    expect(words(detail.get('[data-testid="row-given"]'))).toBe(
      'What it was given — First passage text. Read the full text',
    )
    expect(words(detail.get('[data-testid="row-answer"]'))).toBe('Model’s answer Alone q1 With q1')
    const judges = detail.findAll('[data-testid="row-judge"]')
    expect(words(judges[0]!)).toBe(
      'Judge 1 GPT-5.1 Hallucinated The figure is not in the article. Right Matches the article.',
    )
    expect(words(judges[1]!.get('[data-testid="judge-closed"]'))).toBe('Right')
    expect(words(judges[1]!.get('[data-testid="judge-ctx"]'))).toBe('Right Covers both parts.')
    expect(words(detail.get('[data-testid="row-held"]'))).toBe(
      'Held when challenged Rounds held. Only right answers are challenged. — 1 of 3',
    )
    expect(words(detail.get('[data-testid="row-repeats"]'))).toBe(
      'Right when asked again Out of 4 repeats — 3 of 4',
    )

    await rows[1]!.get('button').trigger('click')
    await flushPromises()
    expect(first.attributes('aria-expanded')).toBe('false')
    expect(wrapper.findAll('[data-testid="question-detail"]')).toHaveLength(1)
  })

  it('links cited pages and flags an answer that did not search', async () => {
    const report = fakeReport()
    report.loadQuestion.mockImplementation(async (_job: string, qaId: string) => {
      const base = questionDetail(qaId)
      return {
        ...base,
        arms: {
          alone: {
            ...base.arms.alone!,
            citations: [
              { url: 'https://www.example.com/story', title: 'Story' },
              { url: 'https://news.test/a', title: null },
              { url: 'javascript:alert(1)', title: 'Bad' },
            ],
          },
          with: { ...base.arms.with!, web_search_unused: true },
        },
      }
    })
    const { wrapper } = await mountPage(report)
    await wrapper.get('[data-testid="question-row"] button').trigger('click')
    await flushPromises()

    const alone = wrapper.get('[data-testid="answer-closed"]')
    const links = alone.findAll('[data-testid="citations"] a')
    expect(links.map((a) => a.text())).toEqual(['Story', 'news.test', 'Bad'])
    expect(links[0]!.attributes('href')).toBe('https://www.example.com/story')
    expect(links[0]!.attributes('target')).toBe('_blank')
    expect(links[2]!.attributes('href')).toBeUndefined()
    expect(alone.find('[data-testid="searched-no"]').exists()).toBe(false)

    const withData = wrapper.get('[data-testid="answer-ctx"]')
    expect(withData.get('[data-testid="searched-no"]').text()).toBe('Searched: no')
    expect(withData.find('[data-testid="citations"]').exists()).toBe(false)
  })

  it('has no verdict override or removal controls', async () => {
    const { wrapper } = await mountPage()
    await wrapper.get('[data-testid="question-row"] button').trigger('click')
    await flushPromises()
    const text = wrapper.text()
    for (const word of ['Change a verdict', 'Remove this question', 'Restore', 'Excluded']) {
      expect(text).not.toContain(word)
    }
  })

  it('opens every passage in a dialog and returns focus on Escape', async () => {
    const { wrapper } = await mountPage()
    await wrapper.get('[data-testid="question-row"] button').trigger('click')
    await flushPromises()
    const read = wrapper.get('[data-testid="read-full-text"]')
    ;(read.element as HTMLElement).focus()
    await read.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]')!
    expect(dialog).not.toBeNull()
    expect(dialog.querySelector('h2')!.textContent).toBe('What the model was given')
    expect(dialog.querySelector('p')!.textContent).toBe('Question q1')
    const excerpts = [...dialog.querySelectorAll('[data-testid="excerpt"]')].map((e) =>
      squash(e.textContent ?? ''),
    )
    expect(excerpts).toEqual(['From “Article A”First passage text.', 'From “b.md”Second.'])

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
    expect(document.activeElement).toBe(read.element)
  })
})
