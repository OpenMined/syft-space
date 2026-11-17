/** One question's audited rows for one model, arranged by arm, check and judge. */
import type {
  BenchmarkCall,
  BenchmarkCitation,
  BenchmarkDenial,
  BenchmarkFragment,
  BenchmarkPrompts,
  BenchmarkRepeats,
  BenchmarkResult,
} from '@/api/types'

/** The judge name the benchmark records on a verdict set by hand. */
export const OWNER = 'owner override'

const ARM_ORDER = ['closed_book', 'model_with_context']
const BLOCK_ORDER = ['direct', 'denial_loop', 'monte_carlo']

export const ARM_TITLE: Record<string, string> = {
  closed_book: 'On its own',
  model_with_context: 'With your data',
}

export const BLOCK_TITLE: Record<string, string> = {
  direct: 'Asked once',
  denial_loop: 'Challenged',
  monte_carlo: 'Asked again',
}

export interface JudgeAudit {
  judge: string
  primary: boolean
  row: BenchmarkResult
  prompts: BenchmarkPrompts | null
}

export interface BlockAudit {
  block: string
  judges: JudgeAudit[]
  denial: BenchmarkDenial | null
  repeats: BenchmarkRepeats | null
}

export interface Retrieval {
  hit: boolean | null
  rank: number | null
  /** Chunks put in the prompt; null when unknown. */
  contextDocs: number | null
  fragmentMaxChars: number | null
  /** Null: nothing was retrieved for this arm. */
  fragments: BenchmarkFragment[] | null
}

export interface ArmAudit {
  arm: string
  answer: string
  answerer: BenchmarkPrompts | null
  call: BenchmarkCall | null
  citations: BenchmarkCitation[]
  webSearchUnused: boolean
  retrieval: Retrieval | null
  blocks: BlockAudit[]
  /** The direct row every figure counts, as the benchmark marks it (`counted`). */
  counted: BenchmarkResult | null
  /** The counted row when the owner set it. */
  override: BenchmarkResult | null
  /** The direct row an override is posted against: the counted one, else any. */
  actionId: string | null
}

function rank(order: string[], key: string): number {
  const at = order.indexOf(key)
  return at < 0 ? order.length : at
}

function newest(rows: BenchmarkResult[]): BenchmarkResult | null {
  return rows.reduce<BenchmarkResult | null>(
    (best, row) => (!best || row.created_at > best.created_at ? row : best),
    null,
  )
}

function groupBy<T>(rows: T[], keyOf: (row: T) => string): Map<string, T[]> {
  const out = new Map<string, T[]>()
  for (const row of rows) {
    const key = keyOf(row)
    out.set(key, [...(out.get(key) ?? []), row])
  }
  return out
}

/** Panel order, primary first; judges outside the panel after, by name. */
function judgeOrder(panel: string[]): (a: string, b: string) => number {
  return (a, b) => rank(panel, a) - rank(panel, b) || a.localeCompare(b)
}

function blockOf(block: string, rows: BenchmarkResult[], panel: string[]): BlockAudit {
  const byJudge = groupBy(
    rows.filter((row) => row.judge_model !== OWNER),
    (row) => row.judge_model,
  )
  const judges = [...byJudge.keys()].sort(judgeOrder(panel)).map((judge) => {
    const row = newest(byJudge.get(judge)!)!
    return { judge, primary: judge === panel[0], row, prompts: row.prompts ?? null }
  })
  const withDenial = rows.find((row) => row.denial)
  const withRepeats = rows.find((row) => row.repeats)
  return {
    block,
    judges,
    denial: withDenial?.denial ?? null,
    repeats: withRepeats?.repeats ?? null,
  }
}

function armOf(arm: string, rows: BenchmarkResult[], panel: string[]): ArmAudit {
  const blocks = [...groupBy(rows, (row) => row.block)]
    .sort(([a], [b]) => rank(BLOCK_ORDER, a) - rank(BLOCK_ORDER, b))
    .map(([block, own]) => blockOf(block, own, panel))
  const direct = rows.filter((row) => row.block === 'direct')
  const counted = direct.find((row) => row.counted) ?? null
  const first = counted ?? direct[0] ?? rows[0]!
  const answerer = rows.map((row) => row.prompts).find((p) => p?.responder_prompt) ?? null
  const searched = rows.find((row) => row.fragments != null || row.retrieval_hit != null)
  return {
    arm,
    answer: first.answer,
    answerer,
    call: first.call ?? null,
    citations: first.citations ?? [],
    webSearchUnused: !!first.web_search_unused,
    retrieval: searched
      ? {
          hit: searched.retrieval_hit ?? null,
          rank: searched.retrieval_rank ?? null,
          contextDocs: searched.context_docs ?? null,
          fragmentMaxChars: searched.fragment_max_chars ?? null,
          fragments: rows.find((row) => row.fragments?.length)?.fragments ?? null,
        }
      : null,
    blocks,
    counted,
    override: counted?.judge_model === OWNER ? counted : null,
    actionId: first.block === 'direct' ? first.id : null,
  }
}

/** One model's arms, in display order. `panel` is the run's judges, primary first. */
export function auditOf(rows: BenchmarkResult[], panel: string[]): ArmAudit[] {
  return [...groupBy(rows, (row) => row.context_mode)]
    .sort(([a], [b]) => rank(ARM_ORDER, a) - rank(ARM_ORDER, b))
    .map(([arm, armRows]) => armOf(arm, armRows, panel))
}

/** Whether the chunk at `index` went into the prompt; null when unknown. */
export function inPrompt(retrieval: Retrieval, index: number): boolean | null {
  return retrieval.contextDocs === null ? null : index < retrieval.contextDocs
}

/** Whether the chunk was shortened before the prompt. */
export function shortened(fragment: BenchmarkFragment): boolean {
  return typeof fragment.chars === 'number' && fragment.chars > fragment.content.length
}

/** Where the question's source chunk ended up, in words. */
export function sourceText(retrieval: Retrieval): string {
  if (!retrieval.hit) return 'Source not found'
  const shown = retrieval.contextDocs === null || (retrieval.rank ?? 0) <= retrieval.contextDocs
  return shown ? `Source #${retrieval.rank}` : `Source #${retrieval.rank}, not in the prompt`
}
