/** Texts for a run in progress: its phase, its step and its plan. */
import type { BenchmarkJob, BenchmarkProgressPlan } from '@/api/types'
import { plural } from '../labels'

const PHASE_TEXT: Record<string, string> = {
  generate: 'Writing questions from your articles.',
  filter: 'Removing what the web already knows.',
  evaluate: 'Asking the models.',
  judge: 'Grading the answers.',
  report: 'Writing up the results.',
}

export function phaseText(phase: string): string {
  return PHASE_TEXT[phase] ?? 'Getting ready.'
}

type JobProgress = Pick<BenchmarkJob, 'state' | 'phase' | 'message' | 'step_done' | 'step_total'>

/** "Running now · step 3 of 10"; while writing, the job's own counts as it sends them. */
export function progressTitle(job: JobProgress): string {
  if (job.state === 'queued') return 'Queued · starts shortly'
  const message = job.message?.trim()
  if (job.phase === 'generate' && message) return `Running now · ${message}`
  return job.step_total ? `Running now · step ${job.step_done} of ${job.step_total}` : 'Running now'
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
