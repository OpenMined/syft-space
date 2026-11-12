import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, nextTick, reactive, ref, shallowRef } from 'vue'
import { flushPromises, mount, RouterLinkStub, type VueWrapper } from '@vue/test-utils'
import type {
  BenchmarkCombineCheck,
  BenchmarkCombinedMember,
  BenchmarkRepeatStats,
  BenchmarkRunReport,
  BenchmarkRunSummary,
  BenchmarkTarget,
} from '@/api/types'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import CombineDialog from '@/components/benchmark/report/CombineDialog.vue'
import { Input } from '@/components/ui/input'
import ChecksPage from '@/components/benchmark/report/ChecksPage.vue'
import QuestionsPage from '@/components/benchmark/report/QuestionsPage.vue'
import RunSummaryPage from '@/components/benchmark/report/RunSummaryPage.vue'
import RunsList from '@/components/benchmark/report/RunsList.vue'
import {
  provideRun,
  provideRunReport,
  type RunContext,
} from '@/components/benchmark/report/context'
import { useShowCombined } from '@/components/benchmark/report/useShowCombined'
import { settingLabel } from '@/components/benchmark/labels'
import type { RunReport, RunsFilters } from '@/components/benchmark/report/useRunReport'
import { hintText } from './hint'
import { OPUS, QWEN, questionDetail, questionRow, runReport, runSummary } from './reportFixtures'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))
vi.mock('vue-sonner', () => ({ toast }))

let wrapper: VueWrapper | null = null

beforeEach(() => {
  document.body.innerHTML = ''
  useShowCombined().value = false
  vi.clearAllMocks()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

// --- runs list --------------------------------------------------------------

function check(extra: Partial<BenchmarkCombineCheck> = {}): BenchmarkCombineCheck {
  return {
    ok: true,
    members: ['a', 'b'],
    settings_hash: 'h',
    differences: [],
    repeated_questions: 0,
    ...extra,
  }
}

function fakeList(runs: BenchmarkRunSummary[]) {
  const filters = reactive<RunsFilters>({ from: '', to: '' })
  return {
    inProgress: ref([]),
    runs: ref(runs),
    total: ref(runs.length),
    page: ref(0),
    filters,
    filtered: computed(() => false),
    target: shallowRef<BenchmarkTarget | null>(null),
    loading: ref(false),
    loaded: ref(true),
    error: ref<string | null>(null),
    refresh: vi.fn(),
    deleteRun: vi.fn().mockResolvedValue(undefined),
    checkCombined: vi.fn(async (_ids: string[]) => check()),
    createCombined: vi.fn(async (_ids: string[], _title?: string) => runSummary('c')),
  }
}

function mountList(report: ReturnType<typeof fakeList>) {
  const Host = defineComponent({
    setup() {
      provideRunReport(report as unknown as RunReport)
      return () => h(RunsList)
    },
  })
  wrapper = mount(Host, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
  return wrapper
}

const combinedRun = (id: string, extra: Partial<BenchmarkRunSummary['combined']> = {}) =>
  runSummary(id, {
    combined: {
      members: 3,
      origin: 'manual',
      period: null,
      period_start: null,
      title: null,
      ...extra,
    },
    combined_into: [],
  })

function dialog(): HTMLElement | null {
  return document.body.querySelector('[data-testid="combine-dialog"]')
}

describe('RunsList combining', () => {
  it('offers Combine once two runs are checked, without opening the run', async () => {
    const report = fakeList([runSummary('a'), runSummary('b'), runSummary('c')])
    const w = mountList(report)
    const boxes = w.findAll('[data-testid="run-select"]')
    expect(boxes).toHaveLength(3)
    expect(w.find('[data-testid="combine"]').exists()).toBe(false)

    await boxes[0]!.trigger('click')
    expect(w.find('[data-testid="combine"]').exists()).toBe(false)
    await boxes[1]!.trigger('click')
    expect(push).not.toHaveBeenCalled()
    expect(w.find('[data-testid="combine"]').exists()).toBe(true)
  })

  it('has no checkbox on a run in progress', () => {
    const report = fakeList([runSummary('a')])
    report.inProgress.value = [
      {
        job_id: 'live',
        state: 'running',
        kind: 'pipeline',
        phase: 'evaluate',
        block: '',
        model: '',
        step_done: 1,
        step_total: 2,
        message: '',
        created_at: '2026-10-01T12:00:00Z',
        started_at: null,
      },
    ] as never
    const w = mountList(report)
    expect(
      w.get('[data-testid="run-in-progress"]').find('[data-testid="run-select"]').exists(),
    ).toBe(false)
  })

  it('checks first, then creates with the title and shows the counts', async () => {
    const report = fakeList([runSummary('a'), runSummary('b')])
    report.checkCombined.mockResolvedValue(check({ repeated_questions: 4 }))
    const w = mountList(report)
    for (const box of w.findAll('[data-testid="run-select"]')) await box.trigger('click')
    await w.get('[data-testid="combine"]').trigger('click')
    await flushPromises()

    expect(report.checkCombined).toHaveBeenCalledWith(['a', 'b'])
    expect(report.createCombined).not.toHaveBeenCalled()
    expect(dialog()!.querySelector('[data-testid="combine-count"]')!.textContent).toBe(
      '2 runs · 4 repeated questions',
    )

    await w.findComponent(CombineDialog).findComponent(Input).setValue('  Week 44 ')
    dialog()!.querySelector<HTMLButtonElement>('[data-testid="combine-confirm"]')!.click()
    await flushPromises()

    expect(report.createCombined).toHaveBeenCalledWith(['a', 'b'], 'Week 44')
    expect(toast.success).toHaveBeenCalledWith('Runs combined')
    expect(w.find('[data-testid="combine"]').exists()).toBe(false)
  })

  it('omits the repeated count when there is none', async () => {
    const report = fakeList([runSummary('a'), runSummary('b')])
    const w = mountList(report)
    for (const box of w.findAll('[data-testid="run-select"]')) await box.trigger('click')
    await w.get('[data-testid="combine"]').trigger('click')
    await flushPromises()
    expect(dialog()!.querySelector('[data-testid="combine-count"]')!.textContent).toBe('2 runs')
  })

  it('shows what differs and does not create', async () => {
    const report = fakeList([runSummary('a'), runSummary('b')])
    report.checkCombined.mockResolvedValue(
      check({
        ok: false,
        differences: [
          {
            field: 'judge_panel',
            values: [
              { job_id: 'a', value: ['m1'] },
              { job_id: 'b', value: 'm2' },
            ],
          },
        ],
      }),
    )
    const w = mountList(report)
    for (const box of w.findAll('[data-testid="run-select"]')) await box.trigger('click')
    await w.get('[data-testid="combine"]').trigger('click')
    await flushPromises()

    const shown = dialog()!
    expect(shown.textContent).toContain('Runs differ')
    const diff = shown.querySelector('[data-testid="combine-difference"]')!
    expect(diff.textContent).toContain('Judges')
    expect(diff.textContent).toContain('["m1"]')
    expect(diff.textContent).toContain('m2')
    expect(shown.querySelector('[data-testid="combine-confirm"]')).toBeNull()
    expect(report.createCombined).not.toHaveBeenCalled()
  })

  it('turns a 422 refusal on create into the differences', async () => {
    const report = fakeList([runSummary('a'), runSummary('b')])
    report.createCombined.mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: 'these runs were not measured the same way',
          differences: [{ field: 'web_check_model', values: [{ job_id: 'a', value: 'x' }] }],
        },
      },
    })
    const w = mountList(report)
    for (const box of w.findAll('[data-testid="run-select"]')) await box.trigger('click')
    await w.get('[data-testid="combine"]').trigger('click')
    await flushPromises()
    dialog()!.querySelector<HTMLButtonElement>('[data-testid="combine-confirm"]')!.click()
    await flushPromises()
    expect(dialog()!.textContent).toContain('Web check model')
    expect(toast.error).not.toHaveBeenCalled()
  })
})

describe('RunsList combined badges', () => {
  it('labels a manual combined run Combined and an automatic one by its period', async () => {
    const report = fakeList([
      combinedRun('m', { title: 'Week 44' }),
      combinedRun('auto', { origin: 'auto', period: '4h', members: 2 }),
    ])
    const w = mountList(report)
    const badges = w.findAll('[data-testid="run-combined"]')
    expect(badges.map((b) => b.text())).toEqual(['Combined', '4h'])
    expect(w.findAll('[data-testid="run-row"]')[0]!.text()).toContain('Week 44')
    expect(await hintText(badges[1]!)).toBe('Combines 2 runs.')
  })

  it('says only a combined run checkbox combines its runs', async () => {
    const report = fakeList([combinedRun('c1'), runSummary('a')])
    const w = mountList(report)
    const [combinedBox, runBox] = w.findAll('[data-testid="run-select"]')
    expect(await hintText(runBox!)).toBeUndefined()
    expect(await hintText(combinedBox!)).toBe('Combining uses its runs.')
  })

  it('asks for members with the toggle and badges a held run', async () => {
    const report = fakeList([
      combinedRun('c1'),
      runSummary('a', { combined_into: [{ job_id: 'c1', title: 'Week 44' }] }),
    ])
    const w = mountList(report)
    expect(w.find('[data-testid="run-held"]').exists()).toBe(false)

    await w.get('[data-testid="show-combined"]').trigger('click')
    expect(useShowCombined().value).toBe(true)
    await nextTick()
    const held = w.get('[data-testid="run-held"]')
    expect(held.text()).toBe('In combined')
    expect(await hintText(held)).toBe('Part of the combined run “Week 44”.')
  })

  it('says the runs stay when deleting a combined run', async () => {
    const report = fakeList([combinedRun('c1')])
    const w = mountList(report)
    await w.get('[data-testid="run-delete"]').trigger('click')
    const confirm = w.findComponent(DeleteConfirmationDialog)
    expect(confirm.props('itemType')).toBe('combined run')
    expect(confirm.props('description')).toContain('its runs stay')
    confirm.vm.$emit('confirm')
    await flushPromises()
    expect(report.deleteRun).toHaveBeenCalledWith('c1')
  })
})

// --- combined run report ----------------------------------------------------

function member(jobId: string, created: string): BenchmarkCombinedMember {
  return {
    job_id: jobId,
    created_at: created,
    started_at: created,
    finished_at: created,
    trigger: 'schedule',
    window_days: 1,
    documents: 7,
    questions: 40,
    cost_usd: 1.5,
    state: 'succeeded',
    stopped: null,
  }
}

const MEMBERS = [member('a', '2026-10-01T06:00:00'), member('b', '2026-10-02T06:00:00')]

function stats(extra: Partial<BenchmarkRepeatStats> = {}): BenchmarkRepeatStats {
  return {
    questions: 5,
    observations: 10,
    graded: 10,
    compared: 5,
    agreed: 4,
    agreement: 0.8,
    right: 6,
    accuracy: 0.6,
    wrong_to_right: 1,
    right_to_wrong: 2,
    ...extra,
  }
}

function runContext(data: BenchmarkRunReport, model: string | null): RunContext {
  const dataRef = shallowRef<BenchmarkRunReport | null>(data)
  return {
    jobId: 'c1',
    slug: 'ep',
    data: dataRef,
    model: computed(() => model),
    modelReport: computed(() => dataRef.value?.models.find((m) => m.model === model) ?? null),
  }
}

function mountWith(component: object, run: RunContext, report: object = {}) {
  const Host = defineComponent({
    setup() {
      provideRunReport(report as unknown as RunReport)
      provideRun(run)
      return () => h(component)
    },
  })
  wrapper = mount(Host, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
  return wrapper
}

describe('Combined run report', () => {
  it('lists the runs with links to each', () => {
    const w = mountWith(RunSummaryPage, runContext(runReport({ members: MEMBERS }), null))
    const rows = w.findAll('[data-testid="member-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toMatch(/1 Oct 2026, \d{2}:\d{2}/)
    expect(rows[0]!.text()).toContain('Scheduled')
    expect(rows[0]!.text()).toContain('$1.50')
    expect(rows[1]!.findComponent(RouterLinkStub).props('to')).toEqual({
      query: { tab: 'results', job: 'b' },
    })
  })

  it('names a re-ask among the runs by its label', () => {
    const members = [MEMBERS[0]!, { ...MEMBERS[1]!, kind: 'reask', label: '4h' }]
    const w = mountWith(RunSummaryPage, runContext(runReport({ members }), null))
    const kinds = w.findAll('[data-testid="member-trigger"]').map((c) => c.text())
    expect(kinds).toEqual(['Scheduled', 'Re-ask · 4h'])
  })

  it('has no Runs section on a single run', () => {
    const w = mountWith(RunSummaryPage, runContext(runReport(), null))
    expect(w.find('[data-testid="members"]').exists()).toBe(false)
    expect(w.find('[data-testid="run-heading"]').text()).toMatch(/^Run of /)
  })

  it('heads a combined run with its title, else as a combined run', () => {
    const info = { members: 2, origin: 'manual' as const, period: null, period_start: null }
    const titled = runReport({
      members: MEMBERS,
      run: runSummary('c1', { combined: { ...info, title: 'Week 44' } }),
    })
    let w = mountWith(RunSummaryPage, runContext(titled, null))
    expect(w.find('[data-testid="run-heading"]').text()).toBe('Week 44')
    w.unmount()
    const untitled = runReport({
      members: MEMBERS,
      run: runSummary('c1', { combined: { ...info, title: null } }),
    })
    w = mountWith(RunSummaryPage, runContext(untitled, null))
    expect(w.find('[data-testid="run-heading"]').text()).toMatch(/^Combined run of /)
  })

  it('labels settings by their setup names, unknown ones by their words', () => {
    expect(settingLabel('judge_policy')).toBe('Same-company rule')
    expect(settingLabel('brand_new_field')).toBe('Brand new field')
  })

  it('shows the repeated questions per arm for the model', async () => {
    const data = runReport({
      members: MEMBERS,
      repeats: {
        questions: 5,
        models: [
          { model: OPUS, alone: stats({ agreement: 0.4 }), with: stats() },
          { model: QWEN, alone: null, with: null },
        ],
      },
    })
    const w = mountWith(ChecksPage, runContext(data, OPUS))
    const block = w.get('[data-testid="check-repeats"]')
    expect(block.text()).toContain('5 questions were asked in more than one run.')
    const lines = block.findAll('[data-testid="repeat-line"]').map((l) =>
      l
        .findAll('th, td')
        .map((c) => c.text())
        .join(' | '),
    )
    expect(lines).toEqual([
      'Repeated | 5 | 5',
      'Agreement | 40% | 80%',
      'Accuracy | 60% | 60%',
      'Wrong → right | 1 | 1',
      'Right → wrong | 2 | 2',
    ])
    expect(await hintText(block.get('[data-testid="repeat-line"] span'))).toBe(
      'Questions this model answered in more than one run.',
    )
  })

  it('hides the repeated questions without repeats', () => {
    const none = mountWith(ChecksPage, runContext(runReport(), OPUS))
    expect(none.find('[data-testid="check-repeats"]').exists()).toBe(false)
    none.unmount()
    const zero = mountWith(
      ChecksPage,
      runContext(runReport({ repeats: { questions: 0, models: [] } }), OPUS),
    )
    expect(zero.find('[data-testid="check-repeats"]').exists()).toBe(false)
  })

  it('names the run of each question and every run’s verdict', async () => {
    const report = {
      revision: ref(0),
      loadQuestions: vi.fn(async () => ({
        items: [questionRow('q1', { job_id: 'b' })],
        total: 1,
        counts: { all: 1, fixed: 1, either: 0, still: 0, worse: 0 },
      })),
      loadQuestion: vi.fn(async () =>
        questionDetail('q1', {
          observations: [
            {
              job_id: 'a',
              created_at: '2026-10-01T06:00:00',
              verdict_alone: 'hallucinate',
              verdict_with: 'correct',
              overridden: false,
            },
            {
              job_id: 'b',
              created_at: '2026-10-02T06:00:00',
              verdict_alone: 'correct',
              verdict_with: null,
              overridden: true,
            },
          ],
        }),
      ),
      loadFragments: vi.fn(async () => []),
    }
    const w = mountWith(QuestionsPage, runContext(runReport({ members: MEMBERS }), OPUS), report)
    await flushPromises()
    expect(w.find('[data-testid="run-column"]').exists()).toBe(true)
    expect(w.get('[data-testid="question-run"]').text()).toMatch(/^2 Oct \d{2}:\d{2}$/)

    await w.get('[data-testid="question-row"] button').trigger('click')
    await flushPromises()
    const rows = w.findAll('[data-testid="row-observation"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toMatch(/1 Oct \d{2}:\d{2}.*Hallucinated.*Right/)
    expect(rows[1]!.text()).toContain('—')
  })

  it('has no Run column on a single run', async () => {
    const report = {
      revision: ref(0),
      loadQuestions: vi.fn(async () => ({
        items: [questionRow('q1')],
        total: 1,
        counts: { all: 1, fixed: 1, either: 0, still: 0, worse: 0 },
      })),
      loadQuestion: vi.fn(async () => questionDetail('q1')),
      loadFragments: vi.fn(async () => []),
    }
    const w = mountWith(QuestionsPage, runContext(runReport(), OPUS), report)
    await flushPromises()
    expect(w.find('[data-testid="run-column"]').exists()).toBe(false)
    expect(w.find('[data-testid="question-run"]').exists()).toBe(false)
  })
})
