import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { BenchmarkRunTiming } from '@/api/types'
import { duration, hasTiming, phaseLabel, roleLabel, runSpan } from '@/components/benchmark/timing'
import { runReport } from './reportFixtures'

vi.mock('@/api/endpoints/benchmarks', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  benchmarksApi: { getRunReport: vi.fn() },
}))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const { default: TimingTable } = await import('@/components/benchmark/TimingTable.vue')
const api = vi.mocked(benchmarksApi)

function timing(over: Partial<BenchmarkRunTiming> = {}): BenchmarkRunTiming {
  return {
    total_s: 6720,
    phases: [
      { phase: 'generate', s: 720 },
      { phase: 'evaluate', s: 4800 },
      { phase: 'judge', s: 1200 },
    ],
    passes: [
      {
        arm: 'closed_book',
        block: 'direct',
        model: 'x-ai/grok-4.6',
        s: 310.4,
        questions: 22,
        stopped: '',
      },
      {
        arm: 'model_with_context',
        block: 'monte_carlo',
        model: 'x-ai/grok-4.6',
        s: 2400,
        questions: 20,
        stopped: 'cancelled',
      },
    ],
    calls: [
      {
        model: 'x-ai/grok-4.6',
        role: 'answer',
        count: 140,
        failed: 0,
        mean_s: 4.2,
        p90_s: 9.81,
        max_s: 31,
        total_s: 588,
      },
      {
        model: 'openai/gpt-5.1',
        role: 'judge',
        count: 300,
        failed: 2,
        mean_s: 0.42,
        p90_s: 1.5,
        max_s: 12,
        total_s: 126,
      },
    ],
    concurrency: { model: 16, endpoint: 2 },
    ...over,
  }
}

describe('timing words', () => {
  it('formats durations by size', () => {
    expect(duration(0.423)).toBe('0.42s')
    expect(duration(8.34)).toBe('8.3s')
    expect(duration(725)).toBe('12m 5s')
    expect(duration(6720)).toBe('1h 52m')
    expect(duration(null)).toBe('—')
    expect(duration(Number.NaN)).toBe('—')
  })

  it('labels phases and roles, passing unknown ones through', () => {
    expect(phaseLabel('evaluate')).toBe('Evaluate')
    expect(phaseLabel('warmup')).toBe('Warmup')
    expect(roleLabel('answer')).toBe('Tested')
    expect(roleLabel('judge')).toBe('Judge')
  })

  it('has nothing to show for null or an empty record', () => {
    expect(hasTiming(null)).toBe(false)
    expect(hasTiming(undefined)).toBe(false)
    expect(hasTiming(timing({ total_s: 0, phases: [], passes: [], calls: [] }))).toBe(false)
    expect(hasTiming(timing())).toBe(true)
  })
})

describe('timing table', () => {
  it('shows phases, passes and call latency', async () => {
    api.getRunReport.mockResolvedValue(runReport({ timing: timing() }))
    const wrapper = mount(TimingTable, { props: { slug: 'news', job: 'j1' } })
    await flushPromises()
    expect(api.getRunReport).toHaveBeenCalledWith('news', 'j1')
    expect(wrapper.find('[data-testid="timing-total"]').text()).toContain('1h 52m')
    expect(wrapper.findAll('[data-testid="timing-phase"]').map((p) => p.text())).toEqual([
      'Generate 12m 0s',
      'Evaluate 1h 20m',
      'Judge 20m 0s',
    ])
    const passes = wrapper.findAll('[data-testid="timing-pass"]')
    expect(passes).toHaveLength(2)
    expect(passes[1]!.text()).toContain('cancelled')
    const calls = wrapper.findAll('[data-testid="timing-call"]')
    expect(calls).toHaveLength(2)
    expect(calls[1]!.text()).toContain('(2 failed)')
    expect(calls[1]!.text()).toContain('0.42s')
  })

  it('shows the cost with the key spend and the span from the job start', async () => {
    const base = runReport({ timing: null })
    api.getRunReport.mockResolvedValue({
      ...base,
      run: { ...base.run, started_at: '2026-09-30T06:10:00Z', finished_at: '2026-09-30T06:50:00Z' },
      method: {
        ...base.method,
        cost: { usd: 1.5, spend_before: 1, spend_after: 2.5, usd_calls: 1.2, total_usd: 1.2 },
      },
    })
    const wrapper = mount(TimingTable, { props: { slug: 'news', job: 'j1' } })
    await flushPromises()
    expect(wrapper.get('[data-testid="timing-total"]').text()).toBe('Total 40m 0s')
    expect(wrapper.get('[data-testid="timing-cost"]').text()).toBe('Cost $1.20(key $1.50)')
  })

  it('is hidden when the run kept no timing', async () => {
    api.getRunReport.mockResolvedValue(runReport({ timing: null }))
    const wrapper = mount(TimingTable, { props: { slug: 'news', job: 'j1' } })
    await flushPromises()
    expect(wrapper.find('[data-testid="timing"]').exists()).toBe(false)
  })

  it('is hidden when the report cannot be read', async () => {
    api.getRunReport.mockRejectedValue(new Error('down'))
    const wrapper = mount(TimingTable, { props: { slug: 'news', job: 'j1' } })
    await flushPromises()
    expect(wrapper.find('[data-testid="timing"]').exists()).toBe(false)
  })
})

describe('runSpan', () => {
  it('measures a run from its timestamps', () => {
    expect(runSpan('2026-10-07T18:00:00Z', '2026-10-07T19:52:00Z')).toBe(6720)
  })
  it('gives null when a timestamp is missing or out of order', () => {
    expect(runSpan(null, '2026-10-07T19:52:00Z')).toBeNull()
    expect(runSpan('2026-10-07T19:52:00Z', '2026-10-07T18:00:00Z')).toBeNull()
  })
})
