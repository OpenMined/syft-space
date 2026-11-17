import { afterEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, shallowRef } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type {
  BenchmarkFilterDecision,
  BenchmarkKindBuild,
  BenchmarkRecordedCall,
  BenchmarkRunPair,
  BenchmarkWriterCall,
} from '@/api/types'
import {
  fateCounts,
  fateOf,
  groupCalls,
  earlierDrafts,
  narrowBlock,
  recordedCall,
  screeningOf,
  statusLabel,
  stepsOf,
} from '@/components/benchmark/report/details/writing'
import { hintText } from './hint'
import { runReport } from './reportFixtures'

vi.mock('@/api/endpoints/benchmarks', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  benchmarksApi: {
    getRunGenerated: vi.fn(),
    getRunPairs: vi.fn(),
    getRunWriting: vi.fn(),
    getRunPair: vi.fn(),
    listRunFilter: vi.fn(),
    updatePairStatus: vi.fn(),
  },
}))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const api = vi.mocked(benchmarksApi)
const GeneratorDialog = (await import('@/components/benchmark/report/details/GeneratorDialog.vue'))
  .default
const QuestionOrigin = (await import('@/components/benchmark/report/details/QuestionOrigin.vue'))
  .default
const RunMethodPage = (await import('@/components/benchmark/report/RunMethodPage.vue')).default
const { provideRun } = await import('@/components/benchmark/report/context')
const { useDetails } = await import('@/components/benchmark/report/details/useDetails')
const { allPages } = await import('@/components/benchmark/report/details/load')

const JOB = 'j1'

function pair(id: string, meta: Record<string, unknown>, over: Partial<BenchmarkRunPair> = {}) {
  return {
    id,
    generator: 'mcq',
    status: 'active',
    status_note: '',
    status_reason: null,
    question: `Question ${id}?`,
    answer: `Answer ${id}`,
    context: 'The passage.',
    document_title: 'Story',
    file_name: 'story.md',
    meta,
    created_at: `2026-10-27T14:41:0${id.slice(-1)}Z`,
    writer_call: null,
    entity_call: null,
    ...over,
  } as BenchmarkRunPair
}

/** The writer call as the benchmark serves it on every pair of the call. */
const WRITER: BenchmarkRecordedCall = {
  call: 'c1',
  model: 'anthropic/claude-opus-5.5',
  system: 'Write questions.',
  user: 'Fragment:\nThe passage.\nGenerate 2.',
  reply: '[{"question": "..."}]',
  passage: 'The passage.',
  cost_usd: 0.01,
  latency_s: 6,
}

const ENTITY_CALL: BenchmarkRecordedCall = {
  call: 'e1',
  model: 'anthropic/claude-opus-5.5',
  system: 'Review.',
  user: 'Questions: ...',
  reply: '[]',
  passage: '',
  cost_usd: null,
  latency_s: null,
}

const WEB = {
  model: 'openai/gpt-5.1',
  judge: 'google/gemini-3.1-pro-preview',
  system: 'Answer the question.',
  user: 'Question p2?',
  answer: 'D) That one',
  verdict: 'correct',
  reasoning: 'matched by the option letter',
  citations: [{ url: 'https://example.com/a', title: 'Example' }],
  web_search_requests: 1,
  judge_system: '',
  judge_prompt: '',
  judge_reply: '',
}

function kindPairs(): BenchmarkRunPair[] {
  const calls = { writer_call: WRITER, entity_call: ENTITY_CALL }
  return [
    pair(
      'p1',
      {
        writer: { call: 'c1' },
        entity_check: {
          call: 'e1',
          outcome: 'kept',
          entities: [{ name: 'Andy Burnham', identifiable: true, why: 'Full name' }],
        },
        screening: [
          {
            job_id: JOB,
            stage: 'grounding',
            outcome: 'removed',
            reason: 'grounding',
            note: 'coverage 50%',
          },
        ],
      },
      { status: 'rejected', status_reason: 'grounding', ...calls },
    ),
    pair(
      'p2',
      {
        writer: { call: 'c1' },
        entity_check: { call: 'e1', outcome: 'kept', entities: [] },
        screening: [
          { job_id: 'other', stage: 'web_check', outcome: 'kept' },
          {
            job_id: JOB,
            stage: 'web_check',
            outcome: 'removed',
            reason: 'web_answerable',
            note: 'web_answerable',
            gate: { model: 'openai/gpt-5.1', system: 'Check.', user: 'Fragments', reply: '{}' },
            web: WEB,
          },
        ],
      },
      { status: 'rejected', status_reason: 'web_answerable', ...calls },
    ),
    pair('p3', {}, { status: 'retired', status_reason: 'rotation' }),
  ]
}

function logged(over: Partial<BenchmarkWriterCall> = {}): BenchmarkWriterCall {
  return {
    call: 'c2',
    generator: 'mcq',
    model: 'anthropic/claude-opus-5.5',
    at: '2026-10-27T14:41:05Z',
    document_title: 'Dropped story',
    file_name: 'dropped.md',
    passage: 'Another passage.',
    system: 'Write questions.',
    user: 'Fragment:\n⟦passage⟧',
    reply: '[]',
    cost_usd: null,
    latency_s: null,
    error: null,
    dropped: [{ question: 'What did this do?', answer: 'It', reason: 'a demonstrative' }],
    ...over,
  }
}

function decision(over: Partial<BenchmarkFilterDecision> = {}): BenchmarkFilterDecision {
  return {
    qa_id: 'old1',
    question: 'An old question?',
    answer: 'Old answer',
    generator: 'mcq',
    stage: 'web_check',
    outcome: 'kept',
    reason: '',
    reason_code: null,
    at: null,
    written_at: '2026-10-20T10:00:00Z',
    earlier: true,
    status: 'active',
    status_note: '',
    web_check: null,
    ...over,
  }
}

describe('reading pair meta', () => {
  it('reads a resolved call, and none when its texts are not kept', () => {
    expect(recordedCall(WRITER)?.prompt).toBe('Fragment:\nThe passage.\nGenerate 2.')
    expect(recordedCall({ ...WRITER, system: '', user: '', reply: '' })).toBeNull()
    expect(recordedCall(null)).toBeNull()
  })

  it('tolerates missing and malformed fields', () => {
    expect(
      screeningOf({ screening: [null, 3, { job_id: JOB, stage: 'grounding' }] }, JOB),
    ).toHaveLength(1)
    expect(screeningOf({ screening: 'x' }, JOB)).toEqual([])
  })

  it('keeps only this job’s records, with the web check and its judge when called', () => {
    const steps = screeningOf(kindPairs()[1]!.meta, JOB)
    expect(steps).toHaveLength(1)
    expect(steps[0]!.gate?.prompt).toBe('Fragments')
    expect(steps[0]!.web?.exchange.reply).toBe('D) That one')
    expect(steps[0]!.web?.judgeCall).toBeNull()
    const judged = screeningOf(
      {
        screening: [{ job_id: JOB, web: { ...WEB, judge_prompt: 'Grade it', judge_reply: '{}' } }],
      },
      JOB,
    )
    expect(judged[0]!.web?.judgeCall?.model).toBe('google/gemini-3.1-pro-preview')
  })

  it('falls back to the inferred decision for a pair without records', () => {
    const steps = stepsOf(
      pair('p9', {}),
      JOB,
      decision({
        earlier: false,
        reason_code: 'grounding',
        outcome: 'removed',
        stage: 'grounding',
      }),
    )
    expect(fateOf(steps)).toBe('grounding')
    expect(fateOf([])).toBe('unchecked')
  })

  it('words the status', () => {
    expect(statusLabel('retired', 'rotation')).toBe('Rotated out')
    expect(statusLabel('rejected', 'web_answerable')).toBe('Removed: Answerable from the web')
    expect(statusLabel('active', null)).toBe('Active')
  })
})

describe('grouping by writer call', () => {
  it('groups by call, merges the log and adds calls only the log knows', () => {
    const blocks = groupCalls(
      kindPairs(),
      [
        logged(),
        logged({
          call: 'c1',
          at: '2026-10-27T14:41:00Z',
          dropped: [{ question: 'Q', answer: 'A', reason: 'duplicate' }],
        }),
      ],
      JOB,
    )
    expect(blocks.map((b) => b.key)).toEqual(['c1', 'pair:p3', 'c2'])
    const [first, unwritten, onlyLog] = blocks
    expect(first!.drafts.map((d) => d.fate)).toEqual(['grounding', 'web_check'])
    expect(first!.dropped).toHaveLength(1)
    expect(first!.writer?.prompt).toBe('Fragment:\nThe passage.\nGenerate 2.')
    expect(first!.drafts[1]!.entityCall?.system).toBe('Review.')
    expect(unwritten!.writer).toBeNull()
    expect(unwritten!.drafts[0]!.fate).toBe('unchecked')
    expect(onlyLog!.drafts).toEqual([])
    expect(onlyLog!.writer?.prompt).toBe('Fragment:\nAnother passage.')
    expect(fateCounts(blocks)).toEqual({ grounding: 1, web_check: 1, unchecked: 1, dropped: 2 })
  })

  it('narrows blocks to one outcome', () => {
    const [first, , onlyLog] = groupCalls(kindPairs(), [logged()], JOB)
    expect(narrowBlock(first!, 'web_check')!.drafts).toHaveLength(1)
    expect(narrowBlock(first!, 'kept')).toBeNull()
    expect(narrowBlock(onlyLog!, 'dropped')!.dropped).toHaveLength(1)
    expect(narrowBlock(first!, null)).toBe(first)
  })

  it('shows the passage the call was built from, not the question’s context', () => {
    const call = { ...WRITER, passage: 'The full passage.' }
    const [block] = groupCalls([pair('p1', {}, { writer_call: call })], [], JOB)
    expect(block!.passage).toBe('The full passage.')
    expect(groupCalls([pair('p1', {})], [], JOB)[0]!.passage).toBe('The passage.')
  })

  it('shows questions written earlier from the decision when the pair is not loaded', () => {
    const drafts = earlierDrafts([decision()], new Map(), JOB)
    expect(drafts.map((d) => [d.id, d.fate, d.pair])).toEqual([['old1', 'kept', null]])
  })
})

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.clearAllMocks()
  useDetails().value = false
  document.body.innerHTML = ''
})

const BUILD: BenchmarkKindBuild = {
  kind: 'mcq',
  unit: 'passage',
  budget: 8,
  written: 16,
  units_available: 124,
  units_read: 8,
  failed_units: 0,
  topped_up: 8,
  dropped: { duplicate: 1 },
  stopped: 'budget reached',
}

function stubApi(writing: BenchmarkWriterCall[] = [logged()]) {
  api.getRunGenerated.mockResolvedValue({ kinds: [BUILD], items: kindPairs(), total: 3 })
  api.getRunPairs.mockResolvedValue({
    items: [pair('old1', {}, { question: 'An old question?' })],
    total: 1,
  })
  api.getRunWriting.mockResolvedValue({ items: writing, total: writing.length })
  api.listRunFilter.mockResolvedValue({
    items: [decision()],
    total: 1,
    counts: { kept: 1, removed: 0, failed: 0 },
  })
}

function body(): HTMLElement {
  return document.body
}

async function click(selector: string, at = 0): Promise<void> {
  body().querySelectorAll<HTMLElement>(selector)[at]!.click()
  await flushPromises()
}

describe('GeneratorDialog', () => {
  it('loads the kind lazily and lays out the summary, calls and earlier questions', async () => {
    stubApi()
    wrapper = mount(GeneratorDialog, {
      props: { slug: 'ep', jobId: JOB, generator: 'mcq', build: BUILD },
      attachTo: document.body,
    })
    await flushPromises()
    expect(api.getRunGenerated).toHaveBeenCalledWith('ep', JOB, {
      generator: 'mcq',
      limit: 200,
      offset: 0,
    })
    expect(api.getRunWriting).toHaveBeenCalledWith('ep', JOB, {
      generator: 'mcq',
      limit: 200,
      offset: 0,
    })
    expect(api.listRunFilter).toHaveBeenCalledTimes(1)
    expect(api.listRunFilter).toHaveBeenCalledWith('ep', JOB, { generator: 'mcq', limit: 0 })
    expect(api.getRunPairs).toHaveBeenCalledWith('ep', JOB, ['old1'])
    expect(body().querySelector('[data-testid="kind-build-stats"]')!.textContent).toContain(
      '16 / 8, 8 topped up',
    )
    const chips = [...body().querySelectorAll('[data-testid="fate-filter"] button')].map((b) =>
      b.textContent!.trim(),
    )
    expect(chips).toEqual([
      'All 5',
      'Kept 1',
      'Removed by web check 1',
      'Removed by grounding 1',
      'No decision 1',
      'Dropped while writing 1',
    ])
    expect(body().querySelectorAll('[data-testid="call-block"]')).toHaveLength(3)
    expect(body().querySelector('[data-testid="exchange"]')).toBeNull()
    expect(body().querySelector('[data-testid="written-earlier"]')!.textContent).toContain(
      'An old question?',
    )
    expect(body().querySelector('[data-testid="dropped-counts"]')).toBeNull()

    await click('[data-testid="fate-web_check"]')
    expect(body().querySelectorAll('[data-testid="call-block"]')).toHaveLength(1)
    expect(body().querySelector('[data-testid="written-earlier"]')).toBeNull()
    await click('[data-testid="call-toggle"]')
    expect(body().querySelectorAll('[data-testid="draft-row"]')).toHaveLength(1)
    await click('[data-testid="draft-toggle"]')
    const path = body().querySelector('[data-testid="filter-path"]')!.textContent!
    expect(path).toContain('Entity check')
    expect(path).toContain('Archive check')
    expect(path).toContain('Web check')
    expect(path).toContain('Verdict: matched by the option letter')
    expect(path).toContain('Removed: Answerable from the web')
  })

  it('shows only the dropped counts for a run without the writing log', async () => {
    stubApi([])
    wrapper = mount(GeneratorDialog, {
      props: { slug: 'ep', jobId: JOB, generator: 'mcq', build: BUILD },
      attachTo: document.body,
    })
    await flushPromises()
    expect(body().querySelector('[data-testid="dropped-counts"]')!.textContent).toContain(
      'duplicate: 1',
    )
    expect(body().querySelector('[data-testid="writing-failed"]')).toBeNull()
  })

  it('says so when the writer calls cannot be loaded', async () => {
    stubApi()
    api.getRunWriting.mockRejectedValue(new Error('500'))
    wrapper = mount(GeneratorDialog, {
      props: { slug: 'ep', jobId: JOB, generator: 'mcq', build: BUILD },
      attachTo: document.body,
    })
    await flushPromises()
    expect(body().querySelector('[data-testid="writing-failed"]')!.textContent).toContain(
      'Could not load the writer calls.',
    )
    expect(body().querySelector('[data-testid="dropped-counts"]')!.textContent).toContain(
      'duplicate: 1',
    )
    expect(body().querySelectorAll('[data-testid="call-block"]').length).toBeGreaterThan(0)
  })

  it('changes a question’s status and reloads', async () => {
    stubApi()
    api.updatePairStatus.mockResolvedValue(kindPairs()[1]!)
    wrapper = mount(GeneratorDialog, {
      props: { slug: 'ep', jobId: JOB, generator: 'mcq', build: BUILD },
      attachTo: document.body,
    })
    await flushPromises()
    await click('[data-testid="call-toggle"]')
    await click('[data-testid="draft-toggle"]', 1)
    const markActive = [...body().querySelectorAll<HTMLElement>('button')].find(
      (b) => b.textContent!.trim() === 'Mark active',
    )!
    markActive.click()
    await flushPromises()
    expect(api.updatePairStatus).toHaveBeenCalledWith('ep', 'p2', 'active')
    expect(api.getRunGenerated).toHaveBeenCalledTimes(2)
  })

  it('says so when the questions written earlier cannot be loaded', async () => {
    stubApi()
    api.getRunPairs.mockRejectedValue(new Error('500'))
    wrapper = mount(GeneratorDialog, {
      props: { slug: 'ep', jobId: JOB, generator: 'mcq', build: BUILD },
      attachTo: document.body,
    })
    await flushPromises()
    const section = body().querySelector('[data-testid="written-earlier"]')!
    expect(section.querySelector('[data-testid="written-earlier-failed"]')!.textContent).toContain(
      'Could not load these questions.',
    )
    expect(section.querySelectorAll('[data-testid="draft-row"]')).toHaveLength(1)
    expect(body().querySelectorAll('[data-testid="call-block"]')).toHaveLength(3)
  })
})

describe('allPages', () => {
  it('reads every page, past 2000 items', async () => {
    const total = 2450
    const fetch = vi.fn(async (offset: number, limit: number) => ({
      items: Array.from({ length: Math.min(limit, total - offset) }, (_, i) => offset + i),
      total,
    }))
    const all = await allPages(fetch)
    expect(all).toHaveLength(total)
    expect(all[total - 1]).toBe(total - 1)
    expect(fetch).toHaveBeenCalledTimes(13)
  })

  it('stops on an empty page', async () => {
    const fetch = vi.fn(async (offset: number) => ({ items: offset ? [] : [1, 2], total: 5 }))
    expect(await allPages(fetch)).toEqual([1, 2])
  })
})

describe('QuestionOrigin', () => {
  it('shows the writer call and the filter path of a later question of the call', async () => {
    api.getRunPair.mockResolvedValue(kindPairs().find((p) => p.id === 'p2')!)
    wrapper = mount(QuestionOrigin, {
      props: { slug: 'ep', jobId: JOB, qaId: 'p2' },
      attachTo: document.body,
    })
    await flushPromises()
    expect(api.getRunPair).toHaveBeenCalledWith('ep', JOB, 'p2')
    const text = wrapper.text()
    expect(text).toContain('Story')
    expect(text).toContain('The passage.')
    expect(text).toContain('Generate 2.')
    expect(text).toContain('[{"question": "..."}]')
    expect(text).toContain('Entity check call')
    expect(wrapper.findAll('[data-testid="filter-step"]').length).toBeGreaterThan(0)
  })

  it('says so when the question cannot be loaded', async () => {
    api.getRunPair.mockRejectedValue(new Error('404'))
    wrapper = mount(QuestionOrigin, {
      props: { slug: 'ep', jobId: JOB, qaId: 'gone' },
      attachTo: document.body,
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Could not load.')
  })
})

describe('RunMethodPage with details', () => {
  function mountPage() {
    const report = runReport()
    report.method.kinds = ['mcq', 'qa']
    const Host = defineComponent({
      setup() {
        provideRun({
          jobId: JOB,
          slug: 'ep',
          data: shallowRef(report),
          model: computed(() => null),
          modelReport: computed(() => null),
        })
        return () => h(RunMethodPage)
      },
    })
    return mount(Host, { attachTo: document.body })
  }

  it('adds the build columns and the kinds missing from the table, in registry order', async () => {
    api.getRunGenerated.mockResolvedValue({
      kinds: [{ ...BUILD, kind: 'false_premise', dropped: {} }, BUILD],
      items: [],
      total: 0,
    })
    useDetails().value = true
    wrapper = mountPage()
    await flushPromises()
    expect(api.getRunGenerated).toHaveBeenCalledWith('ep', JOB, { limit: 1 })
    const rows = wrapper.findAll('[data-testid="kind-row"]').map((r) => r.find('th').text())
    expect(rows).toEqual([
      'Multiple choice',
      'Open questions',
      'Trick questions',
      'Questions with a false premise',
    ])
    expect(wrapper.find('[data-testid="kind-written"]').text()).toBe('16 / 8, 8 topped up')
    const dropped = wrapper.get('[data-testid="kind-dropped"]')
    expect(dropped.attributes('title')).toBeUndefined()
    expect(await hintText(dropped)).toContain('duplicate: 1')
    await wrapper.get('[data-testid="kind-help"]').trigger('click')
    await flushPromises()
    expect(body().querySelector('[data-testid="generator-dialog"]')).not.toBeNull()
  })

  it('stays as it was without details', async () => {
    wrapper = mountPage()
    await flushPromises()
    expect(api.getRunGenerated).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="kind-help"]').exists()).toBe(false)
  })
})
