/** Labels for re-asks: finished runs' questions asked again, the same way. */
import type { BenchmarkReaskInfo } from '@/api/types'
import { plural } from '../labels'

/** A re-ask's name: `Re-ask`, with its label when it has one. */
export function reaskName(label: string | null | undefined): string {
  return label ? `Re-ask · ${label}` : 'Re-ask'
}

export function reaskBadge(info: BenchmarkReaskInfo): string {
  return reaskName(info.label)
}

/** What a re-ask asked again, and of how many runs. */
export function reaskTip(info: BenchmarkReaskInfo): string {
  const judged = info.judges === 'primary' ? ', graded by the first judge only' : ''
  return (
    `Asks the ${plural(info.questions, 'question', 'questions')} of ` +
    `${plural(info.jobs.length, 'run', 'runs')} again, the same way${judged}.`
  )
}
