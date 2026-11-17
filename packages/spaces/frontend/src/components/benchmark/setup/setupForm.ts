/**
 * The Benchmark setup tab as plain data: the page's values, how they are read from
 * the stored layers and written back, and the checks run before save and run.
 *
 * Kept free of Vue so every rule here is testable on its own.
 */
import type {
  BenchmarkInstrumentLayer,
  BenchmarkLayer,
  BenchmarkTarget,
  BenchmarkTargetRequest,
} from '@/api/types'
import { plural } from '../labels'

// --- copy -------------------------------------------------------------------

export interface Choice {
  value: string
  label: string
}

export const DATASET_MODES: Choice[] = [
  { value: 'rolling', label: 'Rolling: only the newest articles' },
  { value: 'incremental', label: 'Growing: add to earlier questions' },
  { value: 'rebuild', label: 'Rebuild: ask the same articles again' },
]

export const JUDGE_POLICIES: Choice[] = [
  { value: 'strict', label: 'Don’t run until it’s fixed' },
  { value: 'warn', label: 'Run anyway and flag the results' },
]

export const TEXT_METRICS: Choice[] = [
  { value: 'bleu', label: 'BLEU' },
  { value: 'rouge', label: 'ROUGE' },
  { value: 'bertscore', label: 'BERTScore' },
]

export const SCHEDULES: Choice[] = [
  { value: '', label: 'Off, run by hand' },
  { value: '24h', label: 'Every day' },
  { value: '12h', label: 'Every 12 hours' },
  { value: '6h', label: 'Every 6 hours' },
  { value: '1h', label: 'Every hour' },
]

export const WEB_ENGINES: Choice[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'native', label: 'Built-in' },
  { value: 'plugin', label: 'OpenRouter plugin' },
]

/** Who settles a question the user returned by hand. */
export const MANUAL_PRIORITIES: Choice[] = [
  { value: 'filter', label: 'The web check decides' },
  { value: 'manual', label: 'Your choice wins' },
]

/** How much judges may think before grading. */
export const JUDGE_REASONING: Choice[] = [
  { value: 'none', label: 'None' },
  { value: 'minimal', label: 'Minimal' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'default', label: 'Model default' },
]

const MAX_JUDGES = 3

/** Settings the page does not show; every save keeps them at these values. */
const FIXED_INSTRUMENT: BenchmarkInstrumentLayer = {
  arms: ['closed_book', 'model_with_context'],
  context_source: 'endpoint_fragments',
  methodology_profile: 'demosyft',
  audit_log: true,
}

// --- write at most ----------------------------------------------------------

/** Passages to read per run so at most `writeAtMost` questions get written. */
export function chunksForBudget(writeAtMost: number, pairsPerChunk: number, kinds: number): number {
  const perPassage = Math.max(1, pairsPerChunk) * Math.max(1, kinds)
  return Math.max(1, Math.ceil(Math.max(0, writeAtMost) / perPassage))
}

/** The "Write at most" figure a stored passage count stands for. */
export function budgetFromChunks(
  chunksPerRun: number,
  pairsPerChunk: number,
  kinds: number,
): number {
  return Math.max(1, chunksPerRun) * Math.max(1, pairsPerChunk) * Math.max(1, kinds)
}

// --- percentages and lists --------------------------------------------------

export function toPercent(share: number): number {
  return Math.round(share * 10000) / 100
}

export function fromPercent(percent: number): number {
  return Math.round(percent * 100) / 10000
}

/** "0.3, 0.9" -> [0.3, 0.9]; null when any part is not a number. */
export function parseNumberList(text: string): number[] | null {
  const parts = text
    .split(/[,;\s]+/)
    .map((part) => part.trim())
    .filter(Boolean)
  if (!parts.length) return null
  const numbers = parts.map(Number)
  return numbers.every((n) => Number.isFinite(n)) ? numbers : null
}

function formatNumberList(values: unknown): string {
  return Array.isArray(values) ? values.join(', ') : ''
}

// --- the page's values ------------------------------------------------------

export interface SetupForm {
  enabled: boolean
  collection: string
  schedule: string
  scheduleAt: string
  // step 1
  windowDays: number
  datasetMode: string
  generateInCycle: boolean
  // step 2
  writer: string
  writeAtMost: number
  /** Kinds left unticked. */
  disabledKinds: string[]
  pairsPerChunk: number
  minChunkChars: number
  answerCoverage: number
  webWriter: boolean
  entityCheck: boolean
  // step 3
  webCheckModel: string
  /** '' means Judge 1. */
  webCheckJudge: string
  keepAtMost: number
  /** 'filter' | 'manual'. */
  manualPriority: string
  // step 4
  models: string[]
  challenge: boolean
  repeat: boolean
  webAlone: boolean
  webWithData: boolean
  webEngine: string
  webMaxResults: number
  /** 0 means the provider's own limit. */
  webMaxSearches: number
  retrievalTopK: number
  contextDocs: number
  fragmentMaxChars: number
  similarityThreshold: number
  denialRounds: number
  repeatSettings: string
  repeatTrials: number
  consistencyFloor: number
  answerMaxTokens: number
  endpointConcurrency: number
  // step 5
  /** Always MAX_JUDGES slots; '' is an empty one. Only the first `judgeCount` count. */
  judges: string[]
  judgeCount: number
  judgePolicy: string
  keyFacts: number
  textMetrics: string[]
  webJudges: boolean
  /** NaN means the model's own default. */
  judgeTemperature: number
  judgeReasoning: string
  // run settings
  maxFailures: number
  /** USD; 0 means no cap. */
  maxJobUsd: number
  reuseAnswers: boolean
  modelConcurrency: number
}

/** What a field falls back to when no layer sets it: the demo values. */
const FALLBACK = {
  document_window_days: 1,
  dataset_mode: 'rolling',
  generate_in_cycle: true,
  chunks_per_run: 0,
  pairs_per_chunk: 2,
  min_chunk_chars: 400,
  answer_coverage_threshold: 0.6,
  dataset_max_pairs: 100,
  retrieval_top_k: 5,
  context_docs: 3,
  fragment_max_chars: 2000,
  similarity_threshold: 0,
  denial_rounds: 3,
  monte_carlo_temperatures: [0.3, 0.9],
  monte_carlo_trials: 3,
  consistency_floor: 0.5,
  answer_max_tokens: 8192,
  endpoint_concurrency: 2,
  judge_policy: 'strict',
  key_facts_threshold: 0.7,
  max_consecutive_failures: 5,
  max_job_usd: 100,
  reuse_answers: true,
} as const

/** The judge temperature value that means the model's own default. */
const MODEL_DEFAULT = 'default'

/** The benchmark's own defaults, shown when no layer sets a field. */
const BENCH_DEFAULTS = {
  web_search_closed_book: true,
  web_search_with_context: false,
  web_search_generator: false,
  entity_check: true,
  web_search_judge: false,
  web_search_engine: 'auto',
  web_search_max_results: 5,
  web_search_max_calls: 0,
  manual_status_priority: 'filter',
  concurrency: 16,
  judge_temperature: 0,
  judge_reasoning_effort: 'low',
} as const

export const MODEL_CONCURRENCY_MAX = 64

/** OpenRouter's own ceiling on server tool calls in one request. */
export const WEB_SEARCHES_MAX = 30

const DEFAULT_WRITE_AT_MOST = 1000

interface Layers {
  /** What the endpoint's own layer inherits: the benchmark's defaults. */
  inheritedProbe: BenchmarkLayer
  inheritedInstrument: BenchmarkLayer
  /** What is in effect: the endpoint's own layer over the inherited one. */
  probe: BenchmarkLayer
  instrument: BenchmarkLayer
}

function layersOf(target: BenchmarkTarget): Layers {
  const inheritedProbe = { ...target.defaults?.probe }
  const inheritedInstrument = { ...target.defaults?.instrument }
  return {
    inheritedProbe,
    inheritedInstrument,
    probe: { ...inheritedProbe, ...target.probe },
    instrument: { ...inheritedInstrument, ...target.instrument },
  }
}

type FallbackKey = keyof typeof FALLBACK | keyof typeof BENCH_DEFAULTS

function fallbackOf(key: FallbackKey): unknown {
  return key in FALLBACK
    ? FALLBACK[key as keyof typeof FALLBACK]
    : BENCH_DEFAULTS[key as keyof typeof BENCH_DEFAULTS]
}

function num(layer: BenchmarkLayer, key: FallbackKey): number {
  const value = layer[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : (fallbackOf(key) as number)
}

function bool(layer: BenchmarkLayer, key: FallbackKey): boolean {
  const value = layer[key]
  return typeof value === 'boolean' ? value : (fallbackOf(key) as boolean)
}

function str(layer: BenchmarkLayer, key: string, fallback = ''): string {
  const value = layer[key]
  return typeof value === 'string' && value ? value : fallback
}

function strings(layer: BenchmarkLayer, key: string): string[] {
  const value = layer[key]
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string' && !!v) : []
}

/** The judges in order, Judge 1 first, no repeats, at most MAX_JUDGES. */
function judgesOf(instrument: BenchmarkLayer): string[] {
  const main = str(instrument, 'judge_model')
  const panel = strings(instrument, 'judge_models')
  const ordered = [...new Set([main, ...panel].filter(Boolean))]
  return ordered.slice(0, MAX_JUDGES)
}

/** The page's values, as the stored layers say they are. */
export function formFromTarget(target: BenchmarkTarget, kinds: string[]): SetupForm {
  const { probe, instrument } = layersOf(target)
  const disabled = strings(probe, 'disabled_generators').filter((key) => kinds.includes(key))
  const enabledKinds = kinds.length - disabled.length
  const pairsPerChunk = num(probe, 'pairs_per_chunk')
  const chunks = num(probe, 'chunks_per_run')
  const blocks = strings(instrument, 'blocks')
  const judges = judgesOf(instrument)
  const policy = str(instrument, 'judge_policy')
  const temperatures = instrument.monte_carlo_temperatures ?? FALLBACK.monte_carlo_temperatures
  const engine = str(instrument, 'web_search_engine', BENCH_DEFAULTS.web_search_engine)
  const priority = str(instrument, 'manual_status_priority')
  const reasoning = str(instrument, 'judge_reasoning_effort', BENCH_DEFAULTS.judge_reasoning_effort)
  const judgeTemperature = instrument.judge_temperature

  return {
    enabled: target.enabled,
    collection: target.collection ?? '',
    schedule: target.schedule ?? '',
    scheduleAt: target.schedule_at ?? '',

    windowDays: num(probe, 'document_window_days'),
    datasetMode: str(probe, 'dataset_mode', FALLBACK.dataset_mode),
    generateInCycle: bool(probe, 'generate_in_cycle'),

    writer: str(instrument, 'generator_model'),
    writeAtMost:
      chunks > 0 ? budgetFromChunks(chunks, pairsPerChunk, enabledKinds) : DEFAULT_WRITE_AT_MOST,
    disabledKinds: disabled,
    pairsPerChunk,
    minChunkChars: num(probe, 'min_chunk_chars'),
    answerCoverage: toPercent(num(instrument, 'answer_coverage_threshold')),
    webWriter: bool(instrument, 'web_search_generator'),
    entityCheck: bool(instrument, 'entity_check'),

    webCheckModel: str(instrument, 'filter_model'),
    webCheckJudge: str(instrument, 'filter_judge_model'),
    keepAtMost: num(probe, 'dataset_max_pairs'),
    manualPriority: priority === 'manual' ? 'manual' : 'filter',

    models: strings(instrument, 'subject_models'),
    challenge: blocks.includes('denial_loop'),
    repeat: blocks.includes('monte_carlo'),
    webAlone: bool(instrument, 'web_search_closed_book'),
    webWithData: bool(instrument, 'web_search_with_context'),
    webEngine: WEB_ENGINES.some((e) => e.value === engine)
      ? engine
      : BENCH_DEFAULTS.web_search_engine,
    webMaxResults: num(instrument, 'web_search_max_results'),
    webMaxSearches: num(instrument, 'web_search_max_calls'),
    retrievalTopK: num(probe, 'retrieval_top_k'),
    contextDocs: num(instrument, 'context_docs'),
    fragmentMaxChars: num(instrument, 'fragment_max_chars'),
    similarityThreshold: num(probe, 'similarity_threshold'),
    denialRounds: num(instrument, 'denial_rounds'),
    repeatSettings: formatNumberList(temperatures),
    repeatTrials: num(instrument, 'monte_carlo_trials'),
    consistencyFloor: toPercent(num(instrument, 'consistency_floor')),
    answerMaxTokens: num(instrument, 'answer_max_tokens'),
    endpointConcurrency: num(probe, 'endpoint_concurrency'),

    judges: [...judges, '', '', ''].slice(0, MAX_JUDGES),
    judgeCount: Math.max(1, judges.length),
    // Only strict and warn are offered; anything else is shown, and saved, as strict.
    judgePolicy: policy === 'warn' ? 'warn' : 'strict',
    keyFacts: toPercent(num(instrument, 'key_facts_threshold')),
    textMetrics: strings(instrument, 'text_metrics'),
    webJudges: bool(instrument, 'web_search_judge'),
    judgeTemperature:
      judgeTemperature === MODEL_DEFAULT ? NaN : num(instrument, 'judge_temperature'),
    judgeReasoning: JUDGE_REASONING.some((c) => c.value === reasoning)
      ? reasoning
      : BENCH_DEFAULTS.judge_reasoning_effort,

    maxFailures: num(instrument, 'max_consecutive_failures'),
    maxJobUsd: num(instrument, 'max_job_usd'),
    reuseAnswers: bool(instrument, 'reuse_answers'),
    modelConcurrency: num(instrument, 'concurrency'),
  }
}

/** One judge picker on the page. */
export interface JudgeSlot {
  /** 0-based. */
  index: number
  id: string
  /** Models the other slots hold. */
  exclude: string[]
  /** Names of tested models from the same company. */
  clashWith: string[]
}

/** The judges that count, Judge 1 first. */
function activeJudges(form: SetupForm): string[] {
  return form.judges.slice(0, form.judgeCount).filter(Boolean)
}

export function enabledKindCount(form: SetupForm, kinds: string[]): number {
  return kinds.filter((key) => !form.disabledKinds.includes(key)).length
}

/** Why the page cannot be saved as it stands; empty when it can. */
export function problemsOf(form: SetupForm, kinds: string[]): string[] {
  const problems: string[] = []
  if (enabledKindCount(form, kinds) < 1) problems.push('Tick at least one kind of question.')
  if (!form.models.length) problems.push('Add at least one model to test.')
  for (let slot = 0; slot < form.judgeCount; slot++) {
    if (!form.judges[slot]) problems.push(`Pick Judge ${slot + 1}.`)
  }
  if (form.repeat && !parseNumberList(form.repeatSettings)) {
    problems.push('Repeat settings must be numbers separated by commas.')
  }
  if (!(form.writeAtMost >= 1)) problems.push('Write at most needs a number of 1 or more.')
  return problems
}

/** Why the page can be saved but not run; empty when it can run. */
export function runProblemsOf(form: Pick<SetupForm, 'webCheckModel'>): string[] {
  return form.webCheckModel.trim() ? [] : ['Choose a web check model.']
}

function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

/**
 * Put a value in the endpoint's own layer, so it stays as saved whatever the
 * layers below it later say. An empty value can't be stored: it is cleared
 * (null over an inherited one, else left out).
 */
function place(layer: BenchmarkLayer, inherited: BenchmarkLayer, key: string, value: unknown) {
  const empty = value === '' || value === undefined || value === null
  if (!empty) layer[key] = value
  else if (inherited[key] === undefined || inherited[key] === null) delete layer[key]
  else layer[key] = null
}

function finite(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

/** The one save: the stored request with every value the page manages placed in it. */
export function buildRequest(
  target: BenchmarkTarget,
  form: SetupForm,
  kinds: string[],
): BenchmarkTargetRequest {
  const {
    inheritedProbe,
    inheritedInstrument,
    probe: effProbe,
    instrument: effInstr,
  } = layersOf(target)
  const probe: BenchmarkLayer = { ...target.probe }
  const instrument: BenchmarkInstrumentLayer = { ...target.instrument }
  const p = (key: string, value: unknown) => place(probe, inheritedProbe, key, value)
  const i = (key: string, value: unknown) => place(instrument, inheritedInstrument, key, value)

  const pairsPerChunk = Math.max(1, finite(form.pairsPerChunk, num(effProbe, 'pairs_per_chunk')))
  const enabledKinds = enabledKindCount(form, kinds)

  p('document_window_days', finite(form.windowDays, num(effProbe, 'document_window_days')))
  p('dataset_mode', form.datasetMode)
  p('generate_in_cycle', form.generateInCycle)
  p('chunks_per_run', chunksForBudget(finite(form.writeAtMost, 1), pairsPerChunk, enabledKinds))
  p(
    'disabled_generators',
    kinds.filter((key) => form.disabledKinds.includes(key)),
  )
  p('pairs_per_chunk', pairsPerChunk)
  p('min_chunk_chars', finite(form.minChunkChars, num(effProbe, 'min_chunk_chars')))
  p('dataset_max_pairs', finite(form.keepAtMost, num(effProbe, 'dataset_max_pairs')))
  p('retrieval_top_k', finite(form.retrievalTopK, num(effProbe, 'retrieval_top_k')))
  p('similarity_threshold', finite(form.similarityThreshold, num(effProbe, 'similarity_threshold')))
  p('endpoint_concurrency', finite(form.endpointConcurrency, num(effProbe, 'endpoint_concurrency')))

  i('generator_model', form.writer)
  i(
    'answer_coverage_threshold',
    fromPercent(finite(form.answerCoverage, toPercent(num(effInstr, 'answer_coverage_threshold')))),
  )
  i('filter_model', form.webCheckModel)
  i('filter_judge_model', form.webCheckJudge)
  i('subject_models', form.models)
  i('blocks', [
    'direct',
    ...(form.challenge ? ['denial_loop'] : []),
    ...(form.repeat ? ['monte_carlo'] : []),
  ])
  i('context_docs', finite(form.contextDocs, num(effInstr, 'context_docs')))
  i('fragment_max_chars', finite(form.fragmentMaxChars, num(effInstr, 'fragment_max_chars')))
  i('denial_rounds', finite(form.denialRounds, num(effInstr, 'denial_rounds')))
  i(
    'monte_carlo_temperatures',
    parseNumberList(form.repeatSettings) ??
      effInstr.monte_carlo_temperatures ??
      FALLBACK.monte_carlo_temperatures,
  )
  i('monte_carlo_trials', finite(form.repeatTrials, num(effInstr, 'monte_carlo_trials')))
  i(
    'consistency_floor',
    fromPercent(finite(form.consistencyFloor, toPercent(num(effInstr, 'consistency_floor')))),
  )
  i('answer_max_tokens', finite(form.answerMaxTokens, num(effInstr, 'answer_max_tokens')))

  const judges = activeJudges(form)
  i('judge_model', judges[0] ?? '')
  i('judge_models', judges)
  i('judge_policy', form.judgePolicy === 'warn' ? 'warn' : 'strict')
  i(
    'key_facts_threshold',
    fromPercent(finite(form.keyFacts, toPercent(num(effInstr, 'key_facts_threshold')))),
  )
  i(
    'text_metrics',
    TEXT_METRICS.map((m) => m.value).filter((m) => form.textMetrics.includes(m)),
  )
  i('max_consecutive_failures', finite(form.maxFailures, num(effInstr, 'max_consecutive_failures')))
  i('max_job_usd', Math.max(0, finite(form.maxJobUsd, num(effInstr, 'max_job_usd'))))
  i('reuse_answers', form.reuseAnswers)

  i('web_search_closed_book', form.webAlone)
  i('web_search_with_context', form.webWithData)
  i('web_search_generator', form.webWriter)
  i('entity_check', form.entityCheck)
  i('web_search_judge', form.webJudges)
  i(
    'web_search_engine',
    WEB_ENGINES.some((e) => e.value === form.webEngine)
      ? form.webEngine
      : BENCH_DEFAULTS.web_search_engine,
  )
  i(
    'web_search_max_results',
    Math.min(
      20,
      Math.max(1, Math.round(finite(form.webMaxResults, BENCH_DEFAULTS.web_search_max_results))),
    ),
  )
  i(
    'web_search_max_calls',
    Math.min(
      WEB_SEARCHES_MAX,
      Math.max(0, Math.round(finite(form.webMaxSearches, num(effInstr, 'web_search_max_calls')))),
    ),
  )
  i('manual_status_priority', form.manualPriority === 'manual' ? 'manual' : 'filter')
  i(
    'concurrency',
    Math.min(
      MODEL_CONCURRENCY_MAX,
      Math.max(1, Math.round(finite(form.modelConcurrency, BENCH_DEFAULTS.concurrency))),
    ),
  )
  // Empty temperature is stored as "default", the model's own; null would mean inherit.
  i(
    'judge_temperature',
    Number.isFinite(form.judgeTemperature)
      ? Math.min(2, Math.max(0, form.judgeTemperature))
      : MODEL_DEFAULT,
  )
  i(
    'judge_reasoning_effort',
    JUDGE_REASONING.some((c) => c.value === form.judgeReasoning)
      ? form.judgeReasoning
      : BENCH_DEFAULTS.judge_reasoning_effort,
  )

  for (const [key, value] of Object.entries(FIXED_INSTRUMENT)) i(key, value)

  return {
    enabled: form.enabled,
    collection: form.collection.trim(),
    probe,
    instrument,
    schedule: form.schedule,
    // The hour only means anything to a daily schedule.
    schedule_at: form.schedule === '24h' ? form.scheduleAt.trim() : '',
  }
}

/** The request as stored now, for telling whether the page holds changes. */
export function storedRequest(target: BenchmarkTarget): BenchmarkTargetRequest {
  return {
    enabled: target.enabled,
    collection: target.collection ?? '',
    probe: { ...target.probe },
    instrument: { ...target.instrument },
    schedule: target.schedule ?? '',
    schedule_at: target.schedule === '24h' ? (target.schedule_at ?? '') : '',
  }
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical((value as Record<string, unknown>)[key])]),
    )
  }
  return value
}

export function sameRequest(a: BenchmarkTargetRequest, b: BenchmarkTargetRequest): boolean {
  return same(canonical(a), canonical(b))
}

// --- summary ----------------------------------------------------------------

/**
 * "9 articles · up to 1000 questions written, 100 kept · 3 models · 3 judges",
 * plus "Monte Carlo skipped: <names>" for tested models that take no temperature.
 */
export function runSummary(
  form: SetupForm,
  articles: number | null,
  monteCarloSkippedNames: string[] = [],
): string {
  const parts: string[] = []
  if (articles !== null) parts.push(plural(articles, 'article'))
  const kept = form.keepAtMost > 0 ? `${form.keepAtMost} kept` : 'all kept'
  parts.push(`up to ${form.writeAtMost} questions written, ${kept}`)
  parts.push(plural(form.models.length, 'model'))
  parts.push(plural(activeJudges(form).length, 'judge'))
  if (monteCarloSkippedNames.length) {
    parts.push(`Monte Carlo skipped: ${monteCarloSkippedNames.join(', ')}`)
  }
  return parts.join(' · ')
}

// --- articles in the window -------------------------------------------------

/** The window to count with: a whole number of days, or undefined for the saved one. */
export function windowDaysParam(value: unknown): number | undefined {
  if (value === '' || value === null || value === undefined) return undefined
  const days = Number(value)
  return Number.isInteger(days) && days >= 0 ? days : undefined
}
