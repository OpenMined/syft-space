/** Typed reads of a run pair, and a kind's pairs grouped by the writer call that wrote them. */
import type {
  BenchmarkCitation,
  BenchmarkDroppedDraft,
  BenchmarkFilterDecision,
  BenchmarkRecordedCall,
  BenchmarkRunPair,
  BenchmarkWebCheck,
  BenchmarkWriterCall,
} from '@/api/types'
import { sortQuestions } from '../../questionOrder'
import { TONE } from '../../labels'
import { stampMs } from '../figures'
import { removedReasonLabel } from '../labels'

type Rec = Record<string, unknown>

function rec(value: unknown): Rec | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Rec) : null
}

function text(r: Rec | null, key: string): string {
  const value = r?.[key]
  return typeof value === 'string' ? value : ''
}

function num(r: Rec | null, key: string): number | null {
  const value = r?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

const PASSAGE_MARK = '⟦passage⟧'

/** One model call as a stage stored it. */
interface ModelCall {
  model: string
  system: string
  prompt: string
  reply: string
  costUsd: number | null
  latencyS: number | null
}

function callOf(r: Rec | null, prefix = '', model = text(r, 'model')): ModelCall | null {
  if (!r) return null
  const call: ModelCall = {
    model,
    system: text(r, `${prefix}system`),
    prompt: text(r, prefix ? `${prefix}prompt` : 'user'),
    reply: text(r, `${prefix}reply`),
    costUsd: num(r, `${prefix}cost_usd`),
    latencyS: num(r, `${prefix}latency_s`),
  }
  return call.system || call.prompt || call.reply ? call : null
}

/** A call the benchmark resolved for a pair; null when none of its texts are kept. */
export function recordedCall(call: BenchmarkRecordedCall | null | undefined): ModelCall | null {
  return call ? callOf({ ...call }) : null
}

/** A logged writer call; the log keeps the prompt with its passage masked. */
function loggedCall(log: BenchmarkWriterCall): ModelCall | null {
  const call = callOf({ ...log })
  return call && { ...call, prompt: call.prompt.split(PASSAGE_MARK).join(log.passage) }
}

export interface Entity {
  name: string
  identifiable: boolean
  why: string
}

interface EntityCheck {
  outcome: string
  entities: Entity[]
}

function entityCheckOf(meta: Rec | null | undefined): EntityCheck | null {
  const r = rec(meta?.entity_check)
  if (!r) return null
  const list = Array.isArray(r.entities) ? r.entities : []
  return {
    outcome: text(r, 'outcome'),
    entities: list
      .map(rec)
      .filter((e): e is Rec => e !== null)
      .map((e) => ({
        name: text(e, 'name'),
        identifiable: e.identifiable !== false,
        why: text(e, 'why'),
      })),
  }
}

interface WebStep {
  exchange: ModelCall
  judge: string
  verdict: string
  reasoning: string
  citations: BenchmarkCitation[]
  searches: number | null
  error: string | null
  /** Null when no judge was called, e.g. an option letter matched. */
  judgeCall: ModelCall | null
}

function webOf(r: Rec | null): WebStep | null {
  if (!r || !text(r, 'model')) return null
  const citations = (Array.isArray(r.citations) ? r.citations : [])
    .map(rec)
    .filter((c): c is Rec => c !== null && Boolean(text(c, 'url')))
    .map((c) => ({ url: text(c, 'url'), title: text(c, 'title') }))
  return {
    exchange: {
      model: text(r, 'model'),
      system: text(r, 'system'),
      prompt: text(r, 'user'),
      reply: text(r, 'answer'),
      costUsd: num(r, 'cost_usd'),
      latencyS: num(r, 'latency_s'),
    },
    judge: text(r, 'judge'),
    verdict: text(r, 'verdict'),
    reasoning: text(r, 'reasoning'),
    citations,
    searches: num(r, 'web_search_requests'),
    error: text(r, 'error') || null,
    judgeCall: callOf(r, 'judge_', text(r, 'judge')),
  }
}

function webFromDecision(w: BenchmarkWebCheck): WebStep {
  return {
    exchange: {
      model: w.model,
      system: '',
      prompt: '',
      reply: w.answer,
      costUsd: null,
      latencyS: null,
    },
    judge: w.judge,
    verdict: w.verdict,
    reasoning: w.reasoning,
    citations: w.citations ?? [],
    searches: w.searches,
    error: w.error,
    judgeCall: null,
  }
}

/** One filter decision with the calls behind it. */
export interface ScreeningStep {
  stage: string
  outcome: string
  /** The reason in words. */
  reason: string
  reasonCode: string | null
  at: string | null
  gate: ModelCall | null
  web: WebStep | null
}

/** The `meta.screening` records one job made, oldest first. */
export function screeningOf(meta: Rec | null | undefined, jobId: string): ScreeningStep[] {
  const list = Array.isArray(meta?.screening) ? meta.screening : []
  return list
    .map(rec)
    .filter((r): r is Rec => r !== null && text(r, 'job_id') === jobId)
    .map((r) => ({
      stage: text(r, 'stage'),
      outcome: text(r, 'outcome'),
      // A screening record keeps the words under `note` and the code under `reason`.
      reason: text(r, 'note'),
      reasonCode: text(r, 'reason') || null,
      at: text(r, 'at') || null,
      gate: callOf(rec(r.gate)),
      web: webOf(rec(r.web)),
    }))
}

/** The job's records on a pair; a pair without records gets the decision's own step. */
export function stepsOf(
  pair: BenchmarkRunPair | null,
  jobId: string,
  decision: BenchmarkFilterDecision | null,
): ScreeningStep[] {
  const own = pair ? screeningOf(pair.meta, jobId) : []
  if (own.length || !decision) return own
  const web =
    webOf(rec(pair?.meta?.web_check)) ??
    (decision.web_check ? webFromDecision(decision.web_check) : null)
  return [
    {
      stage: decision.stage,
      outcome: decision.outcome,
      reason: decision.reason,
      reasonCode: decision.reason_code,
      at: decision.at,
      gate: null,
      web,
    },
  ]
}

/** What became of a question in this job, as one filterable outcome. */
export type Fate =
  | 'kept'
  | 'web_check'
  | 'grounding'
  | 'control'
  | 'writing'
  | 'failed'
  | 'unchecked'
  | 'dropped'

export const FATES: Fate[] = [
  'kept',
  'web_check',
  'grounding',
  'control',
  'writing',
  'failed',
  'unchecked',
  'dropped',
]

const FATE_LABEL: Record<Fate, string> = {
  kept: 'Kept',
  web_check: 'Removed by web check',
  grounding: 'Removed by grounding',
  control: 'Removed by search',
  writing: 'Removed while writing',
  failed: 'Failed',
  unchecked: 'No decision',
  dropped: 'Dropped while writing',
}

const FATE_TONE: Record<Fate, string> = {
  kept: TONE.good,
  web_check: TONE.bad,
  grounding: TONE.bad,
  control: TONE.bad,
  writing: TONE.bad,
  failed: TONE.failed,
  unchecked: TONE.muted,
  dropped: TONE.muted,
}

export function fateLabel(fate: Fate): string {
  return FATE_LABEL[fate]
}

export function fateTone(fate: Fate): string {
  return FATE_TONE[fate]
}

const REMOVING_STAGES = new Set<string>(['web_check', 'grounding', 'control', 'writing'])

/** The last decision decides. */
export function fateOf(steps: readonly ScreeningStep[]): Fate {
  const last = steps[steps.length - 1]
  if (!last) return 'unchecked'
  if (last.outcome === 'kept') return 'kept'
  if (last.outcome === 'failed') return 'failed'
  if (last.outcome === 'removed' && REMOVING_STAGES.has(last.stage)) return last.stage as Fate
  return 'unchecked'
}

const STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  pending: 'Pending',
  rejected: 'Removed',
  retired: 'Retired',
}

/** The question's status today, `Rotated out` rather than `Retired` when the reason says so. */
export function statusLabel(status: string, reason: string | null | undefined): string {
  if (status === 'retired' && reason) return removedReasonLabel(reason)
  if (status === 'rejected' && reason) return `Removed: ${removedReasonLabel(reason)}`
  return STATUS_LABEL[status] ?? status
}

/** One question with what this job did to it. */
export interface DraftView {
  id: string
  question: string
  answer: string
  status: string
  statusReason: string | null
  statusNote: string
  /** Null when only the filter decision is known. */
  pair: BenchmarkRunPair | null
  steps: ScreeningStep[]
  fate: Fate
  entity: EntityCheck | null
  entityCall: ModelCall | null
}

export function draftOf(
  pair: BenchmarkRunPair | null,
  decision: BenchmarkFilterDecision | null,
  jobId: string,
): DraftView | null {
  const source = pair ?? decision
  if (!source) return null
  const steps = stepsOf(pair, jobId, decision)
  const entity = pair ? entityCheckOf(pair.meta) : null
  return {
    id: pair?.id ?? decision!.qa_id,
    question: source.question,
    answer: source.answer,
    status: source.status,
    statusReason: pair?.status_reason ?? null,
    statusNote: source.status_note,
    pair,
    steps,
    fate: fateOf(steps),
    entity,
    entityCall: recordedCall(pair?.entity_call),
  }
}

/** One writer call: its source, the call itself and every draft it produced. */
export interface CallBlock {
  key: string
  call: string | null
  at: string | null
  documentTitle: string
  fileName: string
  passage: string
  writer: ModelCall | null
  error: string | null
  drafts: DraftView[]
  dropped: BenchmarkDroppedDraft[]
}

/** A block's time; blocks without a readable stamp sort last. */
function blockMs(block: CallBlock): number {
  return stampMs(block.at) ?? Number.POSITIVE_INFINITY
}

/**
 * A kind's pairs grouped by their writer call, merged with the writing log by call id; calls
 * only the log knows (every draft dropped) are blocks of their own. Ordered by time.
 */
export function groupCalls(
  pairs: readonly BenchmarkRunPair[],
  writing: readonly BenchmarkWriterCall[],
  jobId: string,
  decisions: ReadonlyMap<string, BenchmarkFilterDecision> = new Map(),
): CallBlock[] {
  const logged = new Map(writing.map((w) => [w.call, w]))
  const blocks = new Map<string, CallBlock>()
  const ordered = sortQuestions(pairs, (p) => ({
    generator: p.generator,
    createdAt: p.created_at,
    id: p.id,
  }))
  for (const pair of ordered) {
    const call = pair.writer_call
    const key = call?.call || `pair:${pair.id}`
    let block = blocks.get(key)
    if (!block) {
      const log = call ? logged.get(call.call) : undefined
      block = {
        key,
        call: call?.call || null,
        at: log?.at ?? pair.created_at,
        documentTitle: pair.document_title || log?.document_title || '',
        fileName: pair.file_name || log?.file_name || '',
        passage: call?.passage || pair.context,
        writer: recordedCall(call),
        error: log?.error ?? null,
        drafts: [],
        dropped: log?.dropped ?? [],
      }
      blocks.set(key, block)
    }
    const draft = draftOf(pair, decisions.get(pair.id) ?? null, jobId)
    if (draft) block.drafts.push(draft)
  }
  for (const log of writing) {
    if (blocks.has(log.call)) continue
    blocks.set(log.call, {
      key: log.call,
      call: log.call,
      at: log.at,
      documentTitle: log.document_title,
      fileName: log.file_name,
      passage: log.passage,
      writer: loggedCall(log),
      error: log.error,
      drafts: [],
      dropped: log.dropped ?? [],
    })
  }
  return [...blocks.values()]
    .map((block, at) => ({ block, at }))
    .sort((a, b) => blockMs(a.block) - blockMs(b.block) || a.at - b.at)
    .map((row) => row.block)
}

/** Questions an earlier job wrote (`decisions` holds only those) and this job filtered, in the question order. */
export function earlierDrafts(
  decisions: readonly BenchmarkFilterDecision[],
  pairs: ReadonlyMap<string, BenchmarkRunPair>,
  jobId: string,
): DraftView[] {
  const ordered = sortQuestions(decisions, (d) => ({
    generator: d.generator,
    createdAt: d.written_at,
    id: d.qa_id,
  }))
  return ordered
    .map((d) => draftOf(pairs.get(d.qa_id) ?? null, d, jobId))
    .filter((d): d is DraftView => d !== null)
    .map((d) => ({ ...d, entity: null, entityCall: null }))
}

/** How many questions reached each outcome; drafts dropped while writing count one each. */
export function fateCounts(
  blocks: readonly CallBlock[],
  earlier: readonly DraftView[] = [],
): Partial<Record<Fate, number>> {
  const out: Partial<Record<Fate, number>> = {}
  const add = (fate: Fate, n = 1) => {
    if (n) out[fate] = (out[fate] ?? 0) + n
  }
  for (const block of blocks) {
    for (const draft of block.drafts) add(draft.fate)
    add('dropped', block.dropped.length)
  }
  for (const draft of earlier) add(draft.fate)
  return out
}

/** A block narrowed to one outcome; null when nothing in it matches. */
export function narrowBlock(block: CallBlock, fate: Fate | null): CallBlock | null {
  if (!fate) return block
  if (fate === 'dropped') return block.dropped.length ? { ...block, drafts: [] } : null
  const drafts = block.drafts.filter((d) => d.fate === fate)
  return drafts.length ? { ...block, drafts, dropped: [] } : null
}
