import type { BenchmarkQuestionGroup } from '@/api/types'

/** The two arms the report compares: `closed` is the model on its own, `ctx` with your data. */
export type Arm = 'closed' | 'ctx'

/** The arm keys the server uses. */
export const ARM_KEY = { closed: 'alone', ctx: 'with' } as const

/** fixed: wrong alone, right with data; either: right both; still: wrong both; worse: right alone only. */
export type Group = BenchmarkQuestionGroup

export const TRICK_GENERATOR = 'unanswerable_property'

export interface SettingRow {
  key: string
  label: string
  value: string | null
}

export interface Held {
  held: number
  of: number
}
