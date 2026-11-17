import { describe, expect, it } from 'vitest'
import type { BenchmarkProgressPlan } from '@/api/types'
import { planText } from '@/components/benchmark/setup/progress'

function plan(over: Partial<BenchmarkProgressPlan> = {}): BenchmarkProgressPlan {
  return {
    questions: 30,
    models: ['openai/gpt-5.1', 'x-ai/grok-4.7'],
    conditions: ['closed_book', 'model_with_context'],
    checks: ['direct', 'denial_loop', 'monte_carlo'],
    skipped_monte_carlo: [],
    ...over,
  }
}

describe('progress plan tooltip', () => {
  it('spells out the plan', () => {
    expect(planText(plan())).toBe('30 questions × 2 models × 2 conditions × 3 checks')
  })

  it('uses singulars and names the Monte Carlo skips', () => {
    const text = planText(
      plan({
        questions: 1,
        models: ['openai/gpt-5.1'],
        conditions: ['closed_book'],
        checks: ['direct'],
        skipped_monte_carlo: ['openai/gpt-5.1'],
      }),
      (id) => id.toUpperCase(),
    )
    expect(text).toBe(
      '1 question × 1 model × 1 condition × 1 check. Monte Carlo skipped: OPENAI/GPT-5.1',
    )
  })

  it('is empty without a plan', () => {
    expect(planText(null)).toBe('')
    expect(planText(undefined)).toBe('')
  })
})
