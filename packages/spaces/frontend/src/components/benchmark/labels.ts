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

/** Setting names as the setup page words them; keys are the benchmark's field names. */
const SETTING_LABEL: Record<string, string> = {
  answer_coverage_threshold: 'Answer words found in the passage',
  answer_max_tokens: 'Longest answer',
  arms: 'Answer modes',
  blocks: 'Question blocks',
  consistency_floor: 'Lowest repeat consistency to trust a result',
  context_docs: 'Excerpts sent with each question',
  context_source: 'Where excerpts come from',
  control_max_share: 'Control share, at most',
  denial_rounds: 'Challenge rounds',
  disabled_generators: 'Kinds of questions left out',
  entity_check: 'Check names in questions',
  filter_judge_model: 'Web check judge',
  filter_model: 'Web check model',
  fragment_max_chars: 'Longest excerpt',
  generator_model: 'Question writer',
  judge_model: 'Judge',
  judge_models: 'Judges',
  judge_panel: 'Judges',
  judge_policy: 'Same-company rule',
  judge_reasoning_effort: 'Judge reasoning',
  judge_temperature: 'Judge temperature',
  key_facts_threshold: 'Facts an explanation must cover',
  manual_status_priority: 'When you return a question by hand',
  monte_carlo_temperatures: 'Repeat settings',
  monte_carlo_trials: 'Repeats per setting',
  retrieval_top_k: 'Excerpts the search returns',
  similarity_threshold: 'Search similarity cut-off',
  subject_models: 'Models tested',
  text_metrics: 'Text similarity scores',
  top_up_passages_per_document: 'Extra passages per article',
  web_check_judge: 'Web check judge',
  web_check_model: 'Web check model',
  web_search_closed_book: 'Models search the web on their own',
  web_search_engine: 'Search engine',
  web_search_generator: 'Question writer searches the web',
  web_search_judge: 'Judges search the web',
  web_search_max_calls: 'Searches per answer',
  web_search_max_results: 'Results per search',
  web_search_with_context: 'Models search the web with your data',
  measured: 'Models were asked',
  members: 'Runs',
  settings_hash: 'Settings',
  state: 'State',
  target: 'Endpoint',
}

/** A setting's display name; an unknown field shows as its words, `runs: …` as a pass. */
export function settingLabel(field: string): string {
  if (field.startsWith('runs: ')) return `Pass ${field.slice(6)}`
  const known = SETTING_LABEL[field]
  if (known) return known
  const words = field.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
