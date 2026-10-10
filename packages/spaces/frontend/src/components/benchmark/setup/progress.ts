/** The run bar's plan tooltip. */
import type { BenchmarkProgressPlan } from '@/api/types'

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/** `30 questions × 2 models × 2 conditions × 3 checks`, plus the Monte Carlo skips. */
export function planText(
  plan: BenchmarkProgressPlan | null | undefined,
  nameOf: (id: string) => string = (id) => id,
): string {
  if (!plan) return ''
  const text = [
    plural(plan.questions, 'question'),
    plural(plan.models.length, 'model'),
    plural(plan.conditions.length, 'condition'),
    plural(plan.checks.length, 'check'),
  ].join(' × ')
  const skipped = plan.skipped_monte_carlo ?? []
  return skipped.length ? `${text}. Monte Carlo skipped: ${skipped.map(nameOf).join(', ')}` : text
}
