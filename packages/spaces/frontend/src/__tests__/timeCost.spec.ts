import { describe, expect, it, vi } from 'vitest'
import {
  costLabel,
  costParts,
  keySpend,
  runDuration,
  startFinishText,
  tookText,
} from '@/components/benchmark/report/timeCost'
import { runHeaderText, usdText } from '@/components/benchmark/report/selectors'
import type { BenchmarkRunCost } from '@/api/types'
import { runReport, runSummary } from './reportFixtures'

vi.mock('@/api/endpoints/benchmarks', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  benchmarksApi: { downloadRunExport: vi.fn() },
}))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const { saveRunExport } = await import('@/components/benchmark/report/useRunReport')

const COST: BenchmarkRunCost = {
  usd: 18.52,
  spend_before: 100,
  spend_after: 118.52,
  usd_calls: 18.4,
  total_usd: 18.4,
  by_role: { writer: 5.1, web_check: 2.3, subjects: 7.6, judges: 3.4 },
}

function method(cost: BenchmarkRunCost | null) {
  return { ...runReport().method, cost }
}

describe('run duration', () => {
  const run = { started_at: '2026-09-30T06:00:00', finished_at: '2026-09-30T06:54:00' }

  it('measures from the job start, naive stamps read as UTC', () => {
    expect(runDuration(run)).toBe(3240)
    expect(runDuration({ started_at: null, finished_at: run.finished_at })).toBeNull()
    expect(runDuration({ finished_at: run.finished_at })).toBeNull()
  })

  it('words the duration in minutes and hours', () => {
    expect(tookText(20)).toBe('<1 min')
    expect(tookText(3240)).toBe('54 min')
    expect(tookText(6720)).toBe('1 h 52 min')
    expect(tookText(7200)).toBe('2 h')
  })

  it('gives start and finish in local time, with the day when it changes', () => {
    expect(startFinishText(run)).toMatch(/^Started \d{2}:\d{2} · finished \d{2}:\d{2}$/)
    expect(
      startFinishText({ started_at: '2026-09-30T06:00:00Z', finished_at: '2026-10-02T06:00:00Z' }),
    ).toMatch(/^Started \d{2}:\d{2} · finished \d+ (Sep|Oct) \d{2}:\d{2}$/)
    expect(startFinishText({ started_at: null, finished_at: null })).toBeNull()
  })
})

describe('run cost', () => {
  it('splits the cost by role in a fixed order', () => {
    const parts = costParts(method(COST))!
    expect(parts.map((p) => [p.label, p.color, p.width])).toEqual([
      ['Writing questions', '#00614F', '27.7%'],
      ['Web check', '#008574', '12.5%'],
      ['Models being tested', '#5FB3A6', '41.3%'],
      ['Judges', '#B7DCD6', '18.5%'],
    ])
    expect(costLabel(parts, usdText)).toBe(
      'Cost by role: Writing questions $5.10, Web check $2.30, Models being tested $7.60, Judges $3.40',
    )
  })

  it('has no split for older runs or a run that spent nothing', () => {
    expect(costParts(method(null))).toBeNull()
    expect(costParts(method({ ...COST, by_role: null }))).toBeNull()
    expect(
      costParts(method({ ...COST, by_role: { writer: 0, web_check: 0, subjects: 0, judges: 0 } })),
    ).toBeNull()
  })

  it('keeps the key spend for the technical view', () => {
    expect(keySpend(method(COST))).toBe(18.52)
    expect(keySpend(method({ ...COST, usd: null }))).toBeNull()
  })
})

describe('run header', () => {
  it('appends the duration and the cost to the articles', () => {
    const text = runHeaderText(
      runReport({
        run: runSummary('j1', {
          articles: 9,
          started_at: '2026-09-30T06:00:00Z',
          finished_at: '2026-09-30T06:54:00Z',
        }),
        method: method(COST),
      }),
    )
    expect(text).toMatch(/^9 articles published .+ · took 54 min · cost \$18\.40$/)
  })

  it('starts with a capital when there are no articles', () => {
    const text = runHeaderText(
      runReport({
        run: runSummary('j1', {
          articles: null,
          window_days: null,
          started_at: '2026-09-30T06:00:00Z',
          finished_at: '2026-09-30T06:54:00Z',
        }),
        method: method(null),
      }),
    )
    expect(text).toBe('Took 54 min')
  })
})

describe('Excel export', () => {
  it('saves the file under the server name, else a readable one', async () => {
    const api = vi.mocked(benchmarksApi)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const names: string[] = []
    click.mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    api.downloadRunExport.mockResolvedValueOnce({ blob: new Blob(['x']), fileName: 'ep-run.xlsx' })
    await saveRunExport('news', 'j1')
    api.downloadRunExport.mockResolvedValueOnce({ blob: new Blob(['x']), fileName: null })
    await saveRunExport('news', 'j1')
    expect(api.downloadRunExport).toHaveBeenCalledWith('news', 'j1')
    expect(names).toEqual(['ep-run.xlsx', 'news-run-j1.xlsx'])
    click.mockRestore()
  })
})
