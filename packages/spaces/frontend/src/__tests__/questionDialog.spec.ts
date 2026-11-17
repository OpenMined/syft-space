import { afterEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, shallowRef } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { BenchmarkResult } from '@/api/types'
import { provideRun, provideRunReport } from '@/components/benchmark/report/context'
import { auditOf, OWNER, sourceText } from '@/components/benchmark/report/details/questionAudit'
import type { RunReport } from '@/components/benchmark/report/useRunReport'
import { GEMINI, GPT, OPUS, runReport } from './reportFixtures'

vi.mock('@/api/endpoints/benchmarks', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  benchmarksApi: { listResults: vi.fn(), overrideVerdict: vi.fn(), withdrawVerdict: vi.fn() },
}))
vi.mock('vue-sonner', () => ({ toast: { error: vi.fn() } }))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const { default: QuestionDialog } = await import(
  '@/components/benchmark/report/details/QuestionDialog.vue'
)
const api = vi.mocked(benchmarksApi)

const CONTEXT = 'Passage one. Passage two.'

let seq = 0
function row(over: Partial<BenchmarkResult> = {}): BenchmarkResult {
  seq += 1
  return {
    id: `r${seq}`,
    qa_id: 'q1',
    question: 'When did it open?',
    answer: 'In 2019.',
    generator: 'qa',
    verdict: 'correct',
    reasoning: '',
    judge_model: GPT,
    context_mode: 'closed_book',
    block: 'direct',
    model: OPUS,
    created_at: `2026-10-27T10:00:${String(seq).padStart(2, '0')}`,
    prompts: {
      responder_system: 'Answer briefly.',
      responder_prompt: 'Q: When did it open?',
      context: '',
      judge_system: 'You grade.',
      judge_prompt: 'Grade this.',
      judge_raw: '{"verdict": "correct"}',
      judged_without_model: false,
    },
    ...over,
  }
}

function withData(over: Partial<BenchmarkResult> = {}): BenchmarkResult {
  return row({
    context_mode: 'model_with_context',
    retrieval_hit: true,
    retrieval_rank: 2,
    context_docs: 1,
    fragment_max_chars: 10,
    fragments: [
      { file_name: 'a.md', score: 0.91, content: 'Passage one.' },
      { file_name: 'b.md', score: 0.82, content: 'Passage tw', chars: 40 },
    ],
    prompts: {
      ...row().prompts!,
      responder_prompt: `Context: ${CONTEXT}\nQ: When did it open?`,
      context: CONTEXT,
    },
    ...over,
  })
}

function rows(): BenchmarkResult[] {
  return [
    row({ judge_model: GEMINI, verdict: 'hallucinate', reasoning: 'Wrong year.' }),
    row({ reasoning: 'Matches.', counted: true }),
    row({
      block: 'denial_loop',
      denial: {
        rounds: 2,
        flipped: true,
        flip_round: 2,
        note: '',
        limit: 3,
        log: [
          { round: 1, objection: 'Are you sure?', answer: 'Yes, 2019.' },
          { round: 2, objection: 'Really?', answer: 'Maybe 2018.' },
        ],
      },
    }),
    row({
      block: 'monte_carlo',
      repeats: {
        trials: 2,
        accuracy: 0.5,
        consistency: 0.5,
        by_temperature: {},
        note: '',
        log: [
          { trial: 1, temperature: 0, answer: '2019', correct: true },
          { trial: 2, temperature: 1, answer: '2017', correct: false },
        ],
      },
    }),
    withData({
      prompts: { ...withData().prompts!, judged_without_model: true, judge_prompt: '' },
    }),
    withData({
      judge_model: OWNER,
      verdict: 'hallucinate',
      reasoning: 'Wrong source.',
      counted: true,
    }),
  ]
}

describe('auditOf', () => {
  it('arranges one model by arm and check, primary judge first', () => {
    const arms = auditOf(rows(), [GPT, GEMINI])
    expect(arms.map((a) => a.arm)).toEqual(['closed_book', 'model_with_context'])
    const [alone, withYourData] = arms
    expect(alone!.blocks.map((b) => b.block)).toEqual(['direct', 'denial_loop', 'monte_carlo'])
    expect(alone!.blocks[0]!.judges.map((j) => [j.judge, j.primary])).toEqual([
      [GPT, true],
      [GEMINI, false],
    ])
    expect(alone!.counted?.verdict).toBe('correct')
    expect(alone!.override).toBeNull()
    expect(alone!.actionId).toBe(alone!.counted!.id)
    expect(withYourData!.counted?.judge_model).toBe(OWNER)
    expect(withYourData!.override).toBe(withYourData!.counted)
    expect(withYourData!.blocks[0]!.judges.map((j) => j.judge)).toEqual([GPT])
    expect(withYourData!.retrieval?.fragments).toHaveLength(2)
    expect(alone!.retrieval).toBeNull()
  })

  it('takes the counted row from the benchmark, not from the judge order', () => {
    const [arm] = auditOf(
      [
        row({ judge_model: 'z/judge', verdict: 'abstain', counted: true }),
        row({ judge_model: 'a/judge', verdict: 'correct', counted: false }),
      ],
      [GPT],
    )
    expect(arm!.blocks[0]!.judges.map((j) => j.judge)).toEqual(['a/judge', 'z/judge'])
    expect(arm!.counted?.judge_model).toBe('z/judge')
    expect(arm!.blocks[0]!.judges[0]!.primary).toBe(false)
  })

  it('has no counted row when the benchmark marks none', () => {
    const [arm] = auditOf([row({ counted: null })], [GPT])
    expect(arm!.counted).toBeNull()
    expect(arm!.actionId).toBe(arm!.blocks[0]!.judges[0]!.row.id)
  })

  it('says where the source ranked', () => {
    const base = { fragmentMaxChars: null, fragments: null }
    expect(sourceText({ ...base, hit: false, rank: null, contextDocs: 5 })).toBe('Source not found')
    expect(sourceText({ ...base, hit: true, rank: 2, contextDocs: 5 })).toBe('Source #2')
    expect(sourceText({ ...base, hit: true, rank: 6, contextDocs: 5 })).toBe(
      'Source #6, not in the prompt',
    )
  })
})

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

function mountDialog() {
  const invalidate = vi.fn()
  const Host = defineComponent({
    setup() {
      provideRunReport({ invalidate } as unknown as RunReport)
      const data = shallowRef(runReport())
      provideRun({
        jobId: 'j1',
        slug: 'ep',
        data,
        model: computed(() => OPUS),
        modelReport: computed(() => null),
      })
      return () =>
        h(QuestionDialog, {
          open: true,
          qaId: 'q1',
          question: 'When did it open?',
          generator: 'qa',
        })
    },
  })
  wrapper = mount(Host, { attachTo: document.body })
  return { invalidate }
}

function body(): HTMLElement {
  return document.body
}

function all(selector: string): HTMLElement[] {
  return [...body().querySelectorAll<HTMLElement>(selector)]
}

async function openTab(arm: string): Promise<void> {
  const tab = body().querySelector<HTMLElement>(`[data-testid="tab-${arm}"]`)!
  tab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
  tab.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
  await flushPromises()
}

describe('QuestionDialog', () => {
  it('loads the audited rows of this question and job', async () => {
    api.listResults.mockResolvedValue({ items: rows(), total: 6 })
    mountDialog()
    await flushPromises()
    expect(api.listResults).toHaveBeenCalledWith('ep', {
      qa_id: 'q1',
      model: OPUS,
      job: 'j1',
      prompts: true,
      limit: 100,
      offset: 0,
    })
    expect(api.listResults).toHaveBeenCalledTimes(1)
  })

  it('pages through the rows of one model', async () => {
    const items = rows()
    api.listResults
      .mockResolvedValueOnce({ items: items.slice(0, 4), total: items.length })
      .mockResolvedValueOnce({ items: items.slice(4), total: items.length })
    mountDialog()
    await flushPromises()
    expect(api.listResults).toHaveBeenCalledTimes(2)
    expect(api.listResults.mock.calls[1]![1]).toMatchObject({ model: OPUS, offset: 4 })
    expect(all('[data-testid^="tab-"]')).toHaveLength(2)
  })

  it('shows the answer call, every judge and the reliability transcripts', async () => {
    api.listResults.mockResolvedValue({ items: rows(), total: 6 })
    mountDialog()
    await flushPromises()
    const answerer = body().querySelector('[data-testid="answerer"]')!
    expect(answerer.textContent).toContain('Answer briefly.')
    expect(answerer.textContent).toContain('In 2019.')
    expect(all('[data-testid="primary-judge"]')).toHaveLength(3)
    const direct = body().querySelector('[data-testid="block-direct"]')!
    expect(direct.textContent).toContain('Wrong year.')
    expect(direct.textContent).toContain('{"verdict": "correct"}')
    const rounds = all('[data-testid="denial-log"] [data-held]')
    expect(rounds.map((r) => r.dataset.held)).toEqual(['true', 'false'])
    expect(body().querySelector('[data-testid="repeats-log"]')!.textContent).toContain(
      'temperature 1',
    )
  })

  it('shows the chunks, the highlighted context and the owner verdict with data', async () => {
    api.listResults.mockResolvedValue({ items: rows(), total: 6 })
    mountDialog()
    await flushPromises()
    await openTab('model_with_context')
    const chunks = all('[data-testid="chunk"]')
    expect(chunks).toHaveLength(2)
    expect(chunks[1]!.textContent).toContain('not in prompt')
    expect(chunks[1]!.textContent).toContain('cut')
    expect(chunks[1]!.querySelector('[data-testid="chunk-source"]')).not.toBeNull()
    expect(body().querySelector('mark, .bg-lime-200\\/70')?.textContent).toBe(CONTEXT)
    expect(body().querySelector('[data-testid="no-judge-call"]')).not.toBeNull()
    expect(body().querySelector('[data-testid="owner-verdict"]')).not.toBeNull()
    expect(
      body().querySelector('[data-testid="counted-verdict"]')!.getAttribute('data-verdict'),
    ).toBe('hallucinate')
  })

  it('records a verdict, then reloads the question and the run', async () => {
    const items = rows()
    const primary = items.find((r) => r.judge_model === GPT && r.block === 'direct')!
    api.listResults.mockResolvedValue({ items, total: items.length })
    api.overrideVerdict.mockResolvedValue(row())
    const { invalidate } = mountDialog()
    await flushPromises()
    body().querySelector<HTMLElement>('[data-testid="change-verdict"]')!.click()
    await flushPromises()
    body().querySelector<HTMLElement>('[data-testid="choice-hallucinate"]')!.click()
    const reason = body().querySelector<HTMLInputElement>('[data-testid="verdict-reason"]')!
    reason.value = 'Off by a year'
    reason.dispatchEvent(new Event('input'))
    await flushPromises()
    body().querySelector<HTMLElement>('[data-testid="save-verdict"]')!.click()
    await flushPromises()
    expect(api.overrideVerdict).toHaveBeenCalledWith(
      'ep',
      primary.id,
      'hallucinate',
      'Off by a year',
    )
    expect(api.listResults).toHaveBeenCalledTimes(2)
    expect(invalidate).toHaveBeenCalledWith('j1')
  })

  it('undoes an owner verdict', async () => {
    const items = rows()
    const owner = items.find((r) => r.judge_model === OWNER)!
    api.listResults.mockResolvedValue({ items, total: items.length })
    api.withdrawVerdict.mockResolvedValue()
    const { invalidate } = mountDialog()
    await flushPromises()
    await openTab('model_with_context')
    body().querySelector<HTMLElement>('[data-testid="undo-verdict"]')!.click()
    await flushPromises()
    expect(api.withdrawVerdict).toHaveBeenCalledWith('ep', owner.id)
    expect(invalidate).toHaveBeenCalledWith('j1')
  })
})
