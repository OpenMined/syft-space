import { inject, provide, type ComputedRef, type InjectionKey, type Ref } from 'vue'
import type { BenchmarkModelReport, BenchmarkRunReport } from '@/api/types'
import type { RunReport } from './useRunReport'

const REPORT_KEY: InjectionKey<RunReport> = Symbol('runReport')
const RUN_KEY: InjectionKey<RunContext> = Symbol('runContext')

/** The run a report page shows, shared by its sections. */
export interface RunContext {
  jobId: string
  slug: string
  data: Ref<BenchmarkRunReport | null>
  /** The model the sections describe: the `model` query param; null on run-wide screens. */
  model: ComputedRef<string | null>
  /** The selected model's figures. */
  modelReport: ComputedRef<BenchmarkModelReport | null>
}

export function provideRunReport(report: RunReport): void {
  provide(REPORT_KEY, report)
}

export function useReport(): RunReport {
  const report = inject(REPORT_KEY)
  if (!report) throw new Error('useReport() called outside ResultsHome')
  return report
}

export function provideRun(run: RunContext): void {
  provide(RUN_KEY, run)
}

export function useRun(): RunContext {
  const run = inject(RUN_KEY)
  if (!run) throw new Error('useRun() called outside RunReport')
  return run
}
