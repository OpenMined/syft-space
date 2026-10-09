import type { BenchmarkBehavior } from '@/api/types'
import { generatorWords, shortModel } from '../labels'
import type { Group } from './types'

export const KIND_LABEL: Record<string, string> = {
  named_entity_masking: 'Names',
  temporal_masking: 'Dates',
  numeric_masking: 'Numbers',
  mcq: 'Multiple choice',
  qa: 'Open questions',
  multihop_synthesis: 'Connecting facts',
  two_truths_one_lie: 'Spotting a false claim',
  false_premise: 'Questions with a false premise',
  tiered_explanation: 'Explaining a story simply',
  unanswerable_property: 'Trick questions',
}

export const KIND_DESC: Record<string, string> = {
  named_entity_masking: 'Fill in a missing name in a sentence from your article.',
  temporal_masking: 'Fill in a missing date.',
  numeric_masking: 'Fill in a missing figure.',
  mcq: 'Pick the right answer from four.',
  qa: 'Answer a direct question in a sentence.',
  multihop_synthesis: 'Combine facts from different parts of a story.',
  two_truths_one_lie: 'Find the one false statement among three.',
  false_premise: 'Notice that the question assumes something that did not happen.',
  tiered_explanation: 'Explain a story for a young reader. Graded on how many key facts it covers.',
  unanswerable_property:
    'Ask for a detail your reporting does not contain. The right response is “I don’t know”.',
}

export function kindLabel(generator: string): string {
  return KIND_LABEL[generator] ?? generatorWords(generator).label
}

export function kindDescription(generator: string): string {
  return KIND_DESC[generator] ?? generatorWords(generator).help ?? ''
}

export const VERDICT_LABEL: Record<string, string> = {
  correct: 'Right',
  abstain: 'Didn’t know',
  hallucinate: 'Hallucinated',
  web_sourced: 'From the web',
  pending: 'Not graded yet',
  technical: 'Not measured',
}

export function verdictLabel(verdict: string): string {
  return VERDICT_LABEL[verdict] ?? verdict
}

export const WEB_SOURCED_TIP = 'Stated facts its web search supports.'

/** Tooltip of a verdict pill; empty when it needs none. */
export function verdictTip(verdict: string | null | undefined): string {
  return verdict === 'web_sourced' ? WEB_SOURCED_TIP : ''
}

/** Pill colours without the border reset, shared by every verdict pill. */
export const VERDICT_COLORS: Record<string, string> = {
  correct: 'bg-primary/10 text-primary',
  abstain: 'bg-muted text-muted-foreground',
  hallucinate: 'bg-warning/20 text-foreground',
  web_sourced: 'bg-sky-500/10 text-sky-700 dark:text-sky-400',
}

/** Badge classes for a verdict pill. */
export function verdictTone(verdict: string): string {
  return `border-transparent ${VERDICT_COLORS[verdict] ?? 'bg-muted text-muted-foreground'}`
}

/** Control questions: graded on how the model behaves, not on a right answer. */
export const CONTROL_KINDS = new Set(['unanswerable_property', 'false_premise'])

export type Behavior = BenchmarkBehavior

const BEHAVIOR_OF: Record<string, Behavior> = {
  abstain: 'declined',
  correct: 'corrected',
  web_sourced: 'web_sourced',
  hallucinate: 'made_up',
}

/**
 * The fine outcome of a control answer: the one the API gives, else derived from the
 * verdict (older rows, overrides). Null for other kinds and non-outcomes.
 */
export function behaviorOf(
  generator: string | null | undefined,
  verdict: string | null | undefined,
  given?: string | null,
): Behavior | null {
  if (!generator || !CONTROL_KINDS.has(generator)) return null
  if (given && given in BEHAVIOR_LABEL) return given as Behavior
  return verdict ? (BEHAVIOR_OF[verdict] ?? null) : null
}

export const BEHAVIOR_LABEL: Record<Behavior, string> = {
  declined: 'Declined',
  corrected: 'Corrected',
  web_sourced: 'From the web',
  made_up: 'Hallucinated',
}

/** A verdict in words: the fine outcome on a control question, else the verdict. */
export function outcomeLabel(
  generator: string | null | undefined,
  verdict: string,
  given?: string | null,
): string {
  const behavior = behaviorOf(generator, verdict, given)
  return behavior ? BEHAVIOR_LABEL[behavior] : verdictLabel(verdict)
}

export const GROUP_LABEL: Record<Group, string> = {
  fixed: 'Your data fixed it',
  either: 'Right either way',
  still: 'Still wrong',
  worse: 'Worse with your data',
}

export const ARM_LABEL = {
  closed: 'On its own',
  ctx: 'With your data',
} as const

const MODEL_NAME: Record<string, string> = {
  'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
}

const VENDOR_NAME: Record<string, string> = {
  anthropic: 'Anthropic',
  qwen: 'Alibaba',
  'x-ai': 'xAI',
  openai: 'OpenAI',
  google: 'Google',
  'meta-llama': 'Meta',
  mistralai: 'Mistral AI',
  deepseek: 'DeepSeek',
  moonshotai: 'Moonshot AI',
  cohere: 'Cohere',
}

const UPPER = new Set(['gpt', 'glm', 'ai'])

function word(token: string): string {
  if (UPPER.has(token)) return token.toUpperCase()
  if (/^\d+(\.\d+)?[bkm]$/i.test(token)) return token.toUpperCase()
  return token.charAt(0).toUpperCase() + token.slice(1)
}

/** A display name from a model id: `anthropic/claude-opus-4.8` → `Claude Opus 4.8`. */
export function modelName(id: string): string {
  const bare = id.replace(/^~/, '')
  const known = MODEL_NAME[bare]
  if (known) return known
  const tokens = shortModel(bare)
    .split(/[-_\s]+/)
    .filter((t) => t && t !== 'preview' && t !== 'latest')
    .flatMap((t) => t.replace(/^([a-z]{2,})(\d)/i, '$1 $2').split(' '))
  if (!tokens.length) return bare
  // `gpt-5.1` keeps its hyphen.
  if (tokens[0]!.toLowerCase() === 'gpt' && tokens.length > 1) {
    return [`GPT-${tokens[1]}`, ...tokens.slice(2).map(word)].join(' ')
  }
  return tokens.map(word).join(' ')
}

export function vendorOf(id: string): string | null {
  const bare = id.replace(/^~/, '')
  const cut = bare.indexOf('/')
  return cut === -1 ? null : bare.slice(0, cut)
}

export function vendorName(id: string): string | null {
  const vendor = vendorOf(id)
  if (!vendor) return null
  return VENDOR_NAME[vendor] ?? vendor.charAt(0).toUpperCase() + vendor.slice(1)
}

export const REMOVED_REASON_LABEL: Record<string, string> = {
  grounding: 'Not supported by the article',
  retrieval_gate: 'Search could not find its passage',
  duplicate: 'Duplicate',
  owner: 'Removed by you',
  rotation: 'Rotated out',
  web_answerable: 'Answerable from the web',
  other: 'Other',
}

export function removedReasonLabel(reason: string): string {
  return REMOVED_REASON_LABEL[reason] ?? reason
}
