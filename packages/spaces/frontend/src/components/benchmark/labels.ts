/** Display words and tones shared by the benchmark's setup and report. */

/** What picking an option at random scores: one over the options. */
const GUESS_RATE: Record<string, number> = {
  mcq: 1 / 4,
  two_truths_one_lie: 1 / 3,
}

export const GUESS_TIP = 'What picking an option at random would score.'

/** "guess 25%" for a kind answered by picking an option; null otherwise. */
export function guessText(generator: string): string | null {
  const rate = GUESS_RATE[generator]
  return rate === undefined ? null : `guess ${Math.round(rate * 100)}%`
}

/** `1 model`, `3 models`, `1,200 articles`; `many` names an irregular plural. */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString('en')} ${n === 1 ? one : many}`
}

/** Chip and pill colours by meaning. */
export const TONE = {
  good: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  info: 'bg-sky-500/10 text-sky-700 dark:text-sky-400',
  caution: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  failed: 'bg-warning/20 text-foreground',
  bad: 'bg-destructive/10 text-destructive',
  muted: 'bg-muted text-muted-foreground',
} as const
