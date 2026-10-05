import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'
import type { BenchmarkRunList } from '@/api/types'
import { dispositionFileName } from '@/api/endpoints/benchmarks'
import { heldOf, progressText, shortStamp } from '@/components/benchmark/report/selectors'
import { points, pointsRange } from '@/components/benchmark/report/figures'
import { modelName, vendorName, verdictLabel } from '@/components/benchmark/report/labels'
import { progress, runReport, runSummary } from './reportFixtures'

vi.mock('@/api/endpoints/benchmarks', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  benchmarksApi: {
    getTarget: vi.fn(),
    listReportRuns: vi.fn(),
    getRunReport: vi.fn(),
    listRunQuestions: vi.fn(),
    getRunQuestion: vi.fn(),
    listQuestionFragments: vi.fn(),
    excludeQuestion: vi.fn(),
    restoreQuestion: vi.fn(),
    downloadRunSummary: vi.fn(),
    publishRun: vi.fn(),
    unpublishRun: vi.fn(),
    overrideVerdict: vi.fn(),
    withdrawVerdict: vi.fn(),
  },
}))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const { useRunReport, POLL_MS, RUNS_PAGE } = await import(
  '@/components/benchmark/report/useRunReport'
)
const api = vi.mocked(benchmarksApi)

function list(extra: Partial<BenchmarkRunList> = {}): BenchmarkRunList {
  return { in_progress: [], items: [runSummary('j1')], total: 1, ...extra }
}

function start() {
  const scope = effectScope()
  const report = scope.run(() => useRunReport('s'))!
  return { report, scope }
}

beforeEach(() => {
  vi.resetAllMocks()
  api.getTarget.mockRejectedValue(new Error('none'))
  api.listReportRuns.mockResolvedValue(list())
})

describe('labels and formatting', () => {
  it('uses the customer verdict wording', () => {
    expect(verdictLabel('correct')).toBe('Right')
    expect(verdictLabel('abstain')).toBe('Didn’t know')
    expect(verdictLabel('hallucinate')).toBe('Made it up')
  })

  it('derives model and vendor names from ids', () => {
    expect(modelName('anthropic/claude-opus-4.8')).toBe('Claude Opus 4.8')
    expect(modelName('qwen/qwen3.8-27b')).toBe('Qwen 3.8 27B')
    expect(modelName('openai/gpt-5.1')).toBe('GPT-5.1')
    expect(modelName('google/gemini-3.1-pro-preview')).toBe('Gemini 3.1 Pro')
    expect(modelName('moonshotai/kimi-k2')).toBe('Kimi K2')
    expect(vendorName('x-ai/grok-4.7')).toBe('xAI')
    expect(vendorName('local-model')).toBeNull()
  })

  it('formats lifts given in points', () => {
    expect(points(47.4)).toBe('+47')
    expect(points(-3)).toBe('−3')
    expect(points(null)).toBe('—')
    expect(pointsRange(47, 70)).toBe('+47 to +70')
    expect(pointsRange(50, 50)).toBe('+50')
  })

  it('reads rounds held', () => {
    expect(heldOf({ rounds: 2, flipped: true, flip_round: 2, limit: 3 })).toEqual({
      held: 1,
      of: 3,
    })
    expect(heldOf({ rounds: 3, flipped: false, flip_round: null, limit: 3 })).toEqual({
      held: 3,
      of: 3,
    })
    expect(heldOf(null)).toBeNull()
  })

  it('describes an in-progress run', () => {
    expect(progressText(progress('q', { state: 'queued' }))).toBe('Queued')
    expect(progressText(progress('r', { phase: 'evaluate', step_done: 3, step_total: 10 }))).toBe(
      'Execute · question 3 of 10',
    )
  })

  it('reads stamps and file names', () => {
    expect(shortStamp('2026-09-30T06:00:00')).toMatch(/^\d{1,2} Sep \d{2}:\d{2}$/)
    expect(shortStamp(null)).toBeNull()
    expect(dispositionFileName('attachment; filename="ep-2026-09-30-0600.docx"')).toBe(
      'ep-2026-09-30-0600.docx',
    )
    expect(dispositionFileName("attachment; filename*=UTF-8''a%20b.docx")).toBe('a b.docx')
    expect(dispositionFileName(undefined)).toBeNull()
  })
})

describe('useRunReport', () => {
  afterEach(() => vi.useRealTimers())

  it('loads the runs list with server-side filters and paging', async () => {
    const { report, scope } = start()
    await vi.waitFor(() => expect(report.runs.value).toHaveLength(1))
    expect(api.listReportRuns).toHaveBeenLastCalledWith('s', {
      from: undefined,
      to: undefined,
      status: undefined,
      limit: RUNS_PAGE,
      offset: 0,
    })

    api.listReportRuns.mockResolvedValue(list({ total: 60 }))
    report.page.value = 2
    await vi.waitFor(() =>
      expect(api.listReportRuns).toHaveBeenLastCalledWith(
        's',
        expect.objectContaining({ offset: 2 * RUNS_PAGE }),
      ),
    )

    report.filters.status = 'published'
    report.filters.from = '2026-09-01'
    await vi.waitFor(() =>
      expect(api.listReportRuns).toHaveBeenLastCalledWith('s', {
        from: '2026-09-01',
        to: undefined,
        status: 'published',
        limit: RUNS_PAGE,
        offset: 0,
      }),
    )
    expect(report.page.value).toBe(0)
    expect(report.filtered.value).toBe(true)
    scope.stop()
  })

  it('polls while a job is in progress and drops its cache when it finishes', async () => {
    vi.useFakeTimers()
    api.listReportRuns
      .mockResolvedValueOnce(list({ in_progress: [progress('j2')] }))
      .mockRejectedValueOnce(new Error('blink'))
      .mockResolvedValueOnce(list({ items: [runSummary('j2'), runSummary('j1')], total: 2 }))
    api.getRunReport.mockResolvedValue(runReport())

    const { report, scope } = start()
    await vi.waitFor(() => expect(report.isRunning('j2')).toBe(true))
    const revision = report.revision.value

    await vi.advanceTimersByTimeAsync(POLL_MS)
    expect(report.isRunning('j2')).toBe(true)

    await vi.advanceTimersByTimeAsync(POLL_MS)
    await nextTick()
    expect(report.isRunning('j2')).toBe(false)
    expect(report.runs.value.map((r) => r.job_id)).toEqual(['j2', 'j1'])
    expect(report.revision.value).toBeGreaterThan(revision)

    await vi.advanceTimersByTimeAsync(POLL_MS * 3)
    expect(api.listReportRuns).toHaveBeenCalledTimes(3)
    scope.stop()
  })

  it('caches a run’s report until an action invalidates it', async () => {
    api.getRunReport.mockResolvedValue(runReport())
    api.excludeQuestion.mockResolvedValue({} as never)
    const { report, scope } = start()
    await report.loadReport('j1')
    await report.loadReport('j1')
    expect(api.getRunReport).toHaveBeenCalledTimes(1)

    await report.excludeQuestion('j1', 'q1', 'Ambiguous', true)
    expect(api.excludeQuestion).toHaveBeenCalledWith('s', 'j1', 'q1', {
      reason: 'Ambiguous',
      retire: true,
    })
    await report.loadReport('j1')
    expect(api.getRunReport).toHaveBeenCalledTimes(2)

    await report.restoreQuestion('j1', 'q1')
    expect(api.restoreQuestion).toHaveBeenCalledWith('s', 'j1', 'q1')
    scope.stop()
  })

  it('caches question details and refetches them after a verdict change', async () => {
    api.getRunQuestion.mockResolvedValue({} as never)
    const { report, scope } = start()
    await report.loadQuestion('j1', 'q1', 'm')
    await report.loadQuestion('j1', 'q1', 'm')
    expect(api.getRunQuestion).toHaveBeenCalledTimes(1)
    await report.overrideVerdict('j1', 'r1', 'abstain', 'why')
    expect(api.overrideVerdict).toHaveBeenCalledWith('s', 'r1', 'abstain', 'why')
    await report.loadQuestion('j1', 'q1', 'm')
    expect(api.getRunQuestion).toHaveBeenCalledTimes(2)
    await report.withdrawOverride('j1', 'ov1')
    expect(api.withdrawVerdict).toHaveBeenCalledWith('s', 'ov1')
    scope.stop()
  })

  it('publishes and unpublishes a run by job, returning refusals', async () => {
    const refused = [
      {
        marketplace_id: 'm',
        marketplace_name: 'Hub',
        success: false,
        supported: true,
        error: 'down',
      },
    ]
    api.publishRun.mockResolvedValue({ published: true, card_id: 'c1', refused })
    api.unpublishRun.mockResolvedValue({ published: false, refused: [] })
    const { report, scope } = start()
    await expect(report.publish('j1')).resolves.toEqual({ refused })
    expect(api.publishRun).toHaveBeenCalledWith('s', 'j1')
    await expect(report.unpublish('j1')).resolves.toEqual({ refused: [] })
    expect(api.unpublishRun).toHaveBeenCalledWith('s', 'j1')
    scope.stop()
  })

  it('saves the summary under the server’s file name', async () => {
    const blob = new Blob(['x'])
    api.downloadRunSummary.mockResolvedValue({ blob, fileName: 'ep-2026.docx' })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const { report, scope } = start()
    await report.downloadSummary('j1')
    expect(api.downloadRunSummary).toHaveBeenCalledWith('s', 'j1')
    const anchor = click.mock.contexts[0] as HTMLAnchorElement
    expect(anchor.download).toBe('ep-2026.docx')
    click.mockRestore()
    scope.stop()
  })
})
