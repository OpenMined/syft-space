<script setup lang="ts">
/**
 * What one launch asked, and what came back — under the question, which is the
 * one thing in it that does not repeat.
 *
 * The same question is put to every arm, under every check, to every model
 * under test, and graded by every judge on the panel. A list cut by arm and
 * check first therefore printed the whole generator list once per cell, the
 * question once per cell, and the answer once per grader — not duplicated data,
 * but one fact shown from nine angles with the fact repeated each time.
 *
 * So the question is written once; under it a tile per model per arm, which is
 * the comparison the arms exist for — the model without this endpoint's
 * material against the model with it, side by side; and inside the tile, the
 * panel as a table, judges down the side and checks across the top.
 *
 * The table is what lets the checks stop repeating the answer. `denial_loop`
 * and `monte_carlo` both record the answer they STARTED from, so printed as
 * rows they were the direct answer twice more. As cells they are what they
 * measured: the rounds held of the rounds put, the share of repeats that came
 * back right — each with the exchange behind it on hover, for a reader
 * checking rather than reading.
 *
 * Fetched in full rather than paged: grouping needs every row in hand.
 * `MAX_FETCH` is a safety stop, not a design limit — past it the list says so
 * instead of quietly truncating.
 */
import { computed, reactive, ref, watch } from 'vue'
import { AlertTriangle, Check, ChevronRight, RotateCcw, UserRound, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { apiErrorDetail } from '@/lib/errors'
import {
  ARMS,
  BLOCKS,
  armTileWords,
  armWords,
  blockCode,
  blockWords,
  generatorWords,
  shortModel,
} from './labels'
import ClampText from './ClampText.vue'
import HoverPanel from './HoverPanel.vue'
import ModelChip from './ModelChip.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from '@/components/ui/dialog'
import type {
  BenchmarkCall,
  BenchmarkFragment,
  BenchmarkPrompts,
  BenchmarkResult,
  BenchmarkVerdict,
} from '@/api/types'

const props = defineProps<{
  slug: string
  refreshKey: number
  /** The known generators, in the benchmark's own order — sets group order. */
  generators?: string[]
  /** One launch's answers; empty — everything this endpoint has. */
  job?: string
}>()

/** What the benchmark records in place of a judge when the owner decides. */
const OWNER = 'owner override'

const PAGE = 100
const MAX_FETCH = 1000
const items = ref<BenchmarkResult[]>([])
const loading = ref(false)
const busyKey = ref<string | null>(null)
const truncated = ref(false)
const openGroups = reactive<Record<string, boolean>>({})

async function load(): Promise<void> {
  loading.value = true
  try {
    const first = await benchmarksApi.listResults(props.slug, {
      job: props.job,
      limit: PAGE,
      offset: 0,
    })
    const all = first.items.slice()
    let offset = PAGE
    while (offset < first.total && offset < MAX_FETCH) {
      const page = await benchmarksApi.listResults(props.slug, {
        job: props.job,
        limit: PAGE,
        offset,
      })
      all.push(...page.items)
      offset += PAGE
    }
    items.value = all
    truncated.value = first.total > all.length
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not load answers'))
  } finally {
    loading.value = false
  }
}

watch([() => props.refreshKey, () => props.job], load, { immediate: true })

const ARM_ORDER = Object.keys(ARMS)
const BLOCK_ORDER = Object.keys(BLOCKS)
const DIRECT = 'direct'

/**
 * The verdicts from worst to best, which is the order a tie is broken in.
 *
 * Two graders split evenly have not decided anything, and a figure has to say
 * something. It says the worse of the two: "the panel could not agree that this
 * was right" is the honest reading, and rounding a disagreement up would make a
 * published number depend on which grader was asked first.
 */
const WORST_FIRST = ['hallucinate', 'abstain', 'correct']

/** The order the shares are read in, worst first — see WORST_FIRST. */
const SHARE_ORDER = ['abstain', 'hallucinate', 'correct']

/**
 * Nothing was measured: the row is about the rig, not about the model. It
 * takes no part in a share, and it is not a vote in the panel.
 */
const TECHNICAL = 'technical'

interface Cell {
  block: string
  row: BenchmarkResult | null
}

interface JudgeRow {
  name: string
  cells: Cell[]
}

/** One model in one arm: what it answered, and what the panel made of it. */
interface Tile {
  key: string
  /** The question this tile answers — what the audit trail is fetched by. */
  qaId: string
  contextMode: string
  model: string
  answer: string
  blocks: string[]
  judges: JudgeRow[]
  /** The panel's decision, by majority, the worse of the two on a split. */
  verdict: string
  /** The owner's own row, where he has already said otherwise. */
  overrideId: string | null
  /** The row an override is recorded against — the direct check's. */
  actionId: string
  /** How the call ended: a cut-off answer is graded like a whole one. */
  call: BenchmarkCall | null
}

interface Question {
  key: string
  question: string
  /** The arms this question was put through — the tile columns. */
  arms: string[]
  models: { model: string; tiles: (Tile | null)[] }[]
  /**
   * Whether anything was retrieved for this question, and how it went. On the
   * question because retrieval is a function of it, not of the tile.
   */
  retrieved: boolean
  retrievalHit: boolean | null
  retrievalRank: number | null
  /**
   * How many of what was found went into the prompt, and the ceiling one
   * chunk's text was cut at. `retrieval_top_k` and `context_docs` are two
   * different numbers, and the gap is invisible in the row.
   */
  contextDocs: number | null
  fragmentMaxChars: number | null
}

function group<T>(rows: T[], keyOf: (row: T) => string): Map<string, T[]> {
  const out = new Map<string, T[]>()
  for (const row of rows) {
    const key = keyOf(row)
    const list = out.get(key)
    if (list) list.push(row)
    else out.set(key, [row])
  }
  return out
}

/** The row that speaks for a (judge, check) pair: the one that stands. */
function standing(rows: BenchmarkResult[]): BenchmarkResult | null {
  const latest = rows.filter((row) => row.is_latest)
  const pick = (latest.length ? latest : rows)
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
  return pick[0] ?? null
}

/** The panel's decision over one check: majority, the worse one on a split. */
function decide(rows: BenchmarkResult[]): string {
  const voices = rows.filter((row) => row.is_latest && row.verdict !== 'pending')
  if (!voices.length) return 'pending'
  // Not a split decision to resolve: the majority rule below would read it
  // as agreement about the answer.
  if (voices.every((row) => row.verdict === TECHNICAL)) return TECHNICAL
  // An override is not a vote in the panel; it stands over the whole of it.
  const owner = voices.find((row) => row.judge_model === OWNER)
  if (owner) return owner.verdict

  const tally = new Map<string, number>()
  for (const row of voices) tally.set(row.verdict, (tally.get(row.verdict) ?? 0) + 1)
  const most = Math.max(...tally.values())
  for (const verdict of WORST_FIRST) {
    if (tally.get(verdict) === most) return verdict
  }
  return voices[0]!.verdict
}

function tileOf(key: string, rows: BenchmarkResult[]): Tile {
  const byBlock = group(rows, (row) => row.block)
  const blocks = [...byBlock.keys()].sort((a, b) => BLOCK_ORDER.indexOf(a) - BLOCK_ORDER.indexOf(b))
  const direct = byBlock.get(DIRECT) ?? rows

  const names = [...new Set(rows.map((row) => row.judge_model).filter(Boolean))].sort((a, b) => {
    // The owner last: the panel is the measurement, his word is what came after.
    if (a === OWNER) return 1
    if (b === OWNER) return -1
    return a.localeCompare(b)
  })

  const byJudgeBlock = group(rows, (row) => `${row.judge_model}||${row.block}`)

  return {
    key,
    qaId: rows[0]!.qa_id,
    contextMode: rows[0]!.context_mode,
    model: rows[0]!.model,
    // Every check started from the direct answer, so this is all of them.
    answer: direct[0]!.answer,
    blocks,
    judges: names.map((name) => ({
      name,
      cells: blocks.map((block) => ({
        block,
        row: standing(byJudgeBlock.get(`${name}||${block}`) ?? []),
      })),
    })),
    call: direct[0]!.call ?? null,
    verdict: decide(direct),
    overrideId: direct.find((row) => row.is_latest && row.judge_model === OWNER)?.id ?? null,
    actionId: direct[0]!.id,
  }
}

function questionOf(key: string, rows: BenchmarkResult[]): Question {
  const arms = [...new Set(rows.map((row) => row.context_mode))].sort(
    (a, b) => ARM_ORDER.indexOf(a) - ARM_ORDER.indexOf(b),
  )
  const byModel = group(rows, (row) => row.model)
  const byArmModel = group(rows, (row) => `${row.context_mode}||${row.model}`)
  // The closed book retrieves nothing and reports null, which is a different
  // fact from a search that came back empty — so the first row that searched
  // at all is the one that speaks for the question.
  const searched = rows.find((row) => row.retrieval_hit !== null && row.retrieval_hit !== undefined)

  return {
    key,
    question: rows[0]!.question,
    arms,
    retrieved: searched !== undefined,
    retrievalHit: searched?.retrieval_hit ?? null,
    retrievalRank: searched?.retrieval_rank ?? null,
    contextDocs: searched?.context_docs ?? null,
    fragmentMaxChars: searched?.fragment_max_chars ?? null,
    models: [...byModel.keys()].sort().map((model) => ({
      model,
      // One tile per arm, in arm order, so a model's answers line up in columns
      // with every other model's — and a blank where an arm was not measured
      // keeps that alignment rather than shifting the row.
      tiles: arms.map((arm) => {
        const own = byArmModel.get(`${arm}||${model}`)
        return own ? tileOf(`${key}||${arm}||${model}`, own) : null
      }),
    })),
  }
}

/**
 * How this generator's questions went, per arm, on the group's own header.
 *
 * Ten generators shut is ten identical rows, and the one worth opening is the
 * one that went badly — which is invisible until it is opened. So the shares
 * that would be read inside are read on the outside, which is also the
 * comparison: the same questions with and without this endpoint's material.
 */
function sharesOf(
  questions: Question[],
  arm: string,
): { shares: { verdict: string; share: number }[]; technical: number } {
  const tally = new Map<string, number>()
  let counted = 0
  let technical = 0
  for (const question of questions) {
    for (const row of question.models) {
      for (const tile of row.tiles) {
        if (!tile || tile.contextMode !== arm) continue
        if (tile.verdict === TECHNICAL) {
          technical += 1
          continue
        }
        if (tile.verdict === 'pending') continue
        tally.set(tile.verdict, (tally.get(tile.verdict) ?? 0) + 1)
        counted += 1
      }
    }
  }
  // Only what happened, in a fixed order. The width is held by the column
  // around them rather than by a reserved place per verdict: a gap where
  // nothing happened is not a fact, and a row of chips with a hole in the
  // middle is harder to read than the same chips packed.
  //
  // The technical ones are a count, never a share: they are out of the
  // denominator, and a percentage would put them back in as an outcome.
  const shares = counted
    ? SHARE_ORDER.filter((verdict) => tally.get(verdict)).map((verdict) => ({
        verdict,
        share: (tally.get(verdict) ?? 0) / counted,
      }))
    : []
  return { shares, technical }
}

/** The arms this listing covers at all — the columns every row is built to. */
const armsSeen = computed(() =>
  [...new Set(items.value.map((row) => row.context_mode))].sort(
    (a, b) => ARM_ORDER.indexOf(a) - ARM_ORDER.indexOf(b),
  ),
)

const groups = computed(() => {
  const byGenerator = group(items.value, (row) => row.generator)
  const order = props.generators ?? []
  const known = order.filter((name) => byGenerator.has(name))
  const rest = [...byGenerator.keys()].filter((name) => !order.includes(name)).sort()

  return [...known, ...rest].map((generator) => {
    const questions = [...group(byGenerator.get(generator)!, (row) => row.qa_id)].map(
      ([key, own]) => questionOf(key, own),
    )
    return {
      generator,
      questions,
      // Over the arms of the WHOLE listing, not this generator's own: a
      // generator that missed one would otherwise shift every column after it.
      summary: armsSeen.value.map((arm) => ({ arm, ...sharesOf(questions, arm) })),
    }
  })
})

const questionCount = computed(() => new Set(items.value.map((row) => row.qa_id)).size)
const answerCount = computed(
  () => new Set(items.value.map((row) => `${row.qa_id}|${row.context_mode}|${row.model}`)).size,
)

/** Spelled out rather than built: Tailwind reads its classes out of the source. */
const COLUMNS = ['sm:grid-cols-1', 'sm:grid-cols-2', 'sm:grid-cols-3'] as const

function columnsFor(count: number): string {
  return COLUMNS[Math.min(count, 3) - 1] ?? COLUMNS[0]
}

function toggle(key: string): void {
  openGroups[key] = !openGroups[key]
}

function generatorLabel(key: string): string {
  return generatorWords(key).label || 'Unknown generator'
}

function verdictTone(verdict: string): string {
  if (verdict === 'correct') return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
  if (verdict === 'hallucinate') return 'bg-destructive/10 text-destructive'
  // `technical` and `pending` share the grey: neither is an outcome.
  return 'bg-muted text-muted-foreground'
}

/** The tooltip on a `technical` verdict: what broke, in its own words. */
function technicalWhy(tile: Tile): string {
  const spoken = tile.judges
    .flatMap((judge) => judge.cells)
    .map((cell) => cell.row?.reasoning)
    .find((text) => text)
  return `Nothing was measured; not in any share.${spoken ? `\n\n${spoken}` : ''}`
}

function share(value: number): string {
  return `${Math.round(value * 100)}%`
}

/**
 * How much pressure the answer took, of how much was put.
 *
 * The loop stops at the objection the model gives in on, so the round it gave
 * in on is not a round it held. Read against the number configured rather than
 * the number put: 4 of 4 is a model that held out, 4 of 12 is a run that
 * stopped early, and as a bare "4" they are the same figure.
 */
function heldRounds(row: BenchmarkResult): string {
  const denial = row.denial
  if (!denial) return ''
  const held = denial.flipped ? Math.max((denial.flip_round ?? 1) - 1, 0) : denial.rounds
  return `${held} of ${denial.limit || denial.rounds}`
}

/**
 * Why a check that ran has no figure.
 *
 * Pressure is only ever put on a correct answer — there is nothing to take away
 * from a wrong one, still less from an abstention — so a model that abstained
 * has a row for the check and nothing in it. A bare dash reads as a fault; it
 * is the measurement working as designed.
 */
function emptyWhy(block: string): string {
  if (block === 'denial_loop') return 'Nothing to push at — this answer was not correct'
  if (block === 'monte_carlo') return 'The repeats recorded no figure'
  return ''
}

/**
 * Whether the answer to one objection was still the right one.
 *
 * Not recorded per round, and it does not need to be: the loop stops at the
 * first round it loses, so every round before the one it gave in on was held,
 * and if it never gave in, all of them were.
 */
function heldAt(row: BenchmarkResult, round: number): boolean {
  const denial = row.denial
  if (!denial?.flipped) return true
  return round < (denial.flip_round ?? round + 1)
}
/**
 * Record what the owner says this answer was.
 *
 * Against the direct check, which is what the panel's decision above is about:
 * giving an answer up under pressure and getting it right when asked once are
 * verdicts on two different things. Which of the panel's rows it is sent with
 * makes no difference — the benchmark's override stands over the whole panel.
 * The list is read again afterwards because an override is a new row, not a
 * change to the one it was sent with.
 */
async function override(tile: Tile, verdict: BenchmarkVerdict): Promise<void> {
  const reasoning = window.prompt('Why? (shown next to the verdict)', '') ?? ''
  busyKey.value = tile.key
  try {
    await benchmarksApi.overrideVerdict(props.slug, tile.actionId, verdict, reasoning)
    await load()
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not override this verdict'))
  } finally {
    busyKey.value = null
  }
}

/**
 * Take back what the owner said, leaving the panel's own decision standing.
 *
 * Two buttons that each only ever add a further override would make a misclick
 * permanent: whatever he pressed next would stand over the panel just as the
 * first press did, and there would be no way back to "what the graders
 * decided". This is that way back.
 */
async function undo(tile: Tile): Promise<void> {
  if (!tile.overrideId) return
  busyKey.value = tile.key
  try {
    await benchmarksApi.withdrawVerdict(props.slug, tile.overrideId)
    await load()
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not take this verdict back'))
  } finally {
    busyKey.value = null
  }
}

/* --------------------------------------------------------------------------
 * What was actually sent.
 *
 * Too heavy for the listing — each field runs to tens of thousands of
 * characters — so fetched a question at a time, the first time something asks,
 * and kept. One request serves both the chunks band and every tile's prompt.
 * ------------------------------------------------------------------------ */
const detail = reactive<Record<string, BenchmarkResult[]>>({})
const detailBusy = reactive<Record<string, boolean>>({})
const openContext = reactive<Record<string, boolean>>({})
const promptFor = ref<Tile | null>(null)

async function loadDetail(qaId: string): Promise<void> {
  if (detail[qaId] || detailBusy[qaId]) return
  detailBusy[qaId] = true
  try {
    const page = await benchmarksApi.listResults(props.slug, {
      qa_id: qaId,
      job: props.job,
      limit: PAGE,
      prompts: true,
    })
    detail[qaId] = page.items
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not load what was sent'))
  } finally {
    detailBusy[qaId] = false
  }
}

function toggleContext(question: Question): void {
  openContext[question.key] = !openContext[question.key]
  if (openContext[question.key]) void loadDetail(question.key)
}

function showPrompt(tile: Tile): void {
  promptFor.value = tile
  void loadDetail(tile.qaId)
}

/**
 * The chunks the search returned for a question. The search runs on the
 * question, so the first row that kept them speaks for all of them.
 */
function fragmentsOf(question: Question): BenchmarkFragment[] {
  for (const row of detail[question.key] ?? []) {
    if (row.fragments?.length) return row.fragments
  }
  return []
}

interface JudgeExchange {
  key: string
  name: string
  block: string
  system: string
  prompt: string
  raw: string
  /** The verdict cost no call — nothing was asked, rather than nothing kept. */
  none: boolean
}

/**
 * One tile's exchanges: what the model was asked, and what each judge was.
 *
 * The answerer's side is identical on every row of a tile — one call, copied
 * to each grader's record — so it is written once. A grader never called says
 * so rather than showing an empty box.
 */
const promptPanel = computed<{ answerer: BenchmarkPrompts | null; judges: JudgeExchange[] } | null>(
  () => {
    const tile = promptFor.value
    if (!tile) return null
    const rows = detail[tile.qaId]
    if (!rows) return null

    const kept = new Map(rows.map((row) => [row.id, row.prompts ?? null]))
    let answerer: BenchmarkPrompts | null = null
    const judges: JudgeExchange[] = []

    for (const judge of tile.judges) {
      for (const cell of judge.cells) {
        const own = cell.row ? kept.get(cell.row.id) : null
        if (!own) continue
        if (!answerer && cell.block === DIRECT && own.responder_prompt) answerer = own
        // An owner's override is a row with an audit record and no judging in
        // it. Skipped rather than printed as a grader who was asked nothing.
        if (!own.judge_prompt && !own.judged_without_model) continue
        judges.push({
          key: `${judge.name}||${cell.block}`,
          name: judge.name,
          block: cell.block,
          system: own.judge_system,
          prompt: own.judge_prompt,
          raw: own.judge_raw,
          none: own.judged_without_model,
        })
      }
    }
    return { answerer, judges }
  },
)

/**
 * The prompt, split so the part the search put into it can be marked in
 * place — rather than printed a second time below it.
 */
function promptParts(prompts: BenchmarkPrompts): { text: string; fromData: boolean }[] {
  const text = prompts.responder_prompt
  const context = prompts.context
  const at = context ? text.indexOf(context) : -1
  if (at < 0) return [{ text, fromData: false }]
  const parts = [{ text: context, fromData: true }]
  if (at > 0) parts.unshift({ text: text.slice(0, at), fromData: false })
  const rest = text.slice(at + context.length)
  if (rest) parts.push({ text: rest, fromData: false })
  return parts
}

/**
 * The search material, where it could not be marked inside the prompt: both
 * are cut at their own ceiling, so a long prompt can end before this does.
 */
function strayContext(prompts: BenchmarkPrompts): string {
  if (!prompts.context) return ''
  return prompts.responder_prompt.includes(prompts.context) ? '' : prompts.context
}

function judgeWords(name: string): string {
  return name === OWNER ? 'the owner' : shortModel(name)
}

/** The tooltip on the cut-off mark. */
function cutOffWhy(call: BenchmarkCall): string {
  const ceiling = call.max_tokens ? ` of ${call.max_tokens} tokens` : ''
  return `Cut off at the ceiling${ceiling}; the verdict covers what fitted.`
}

/** Whether this chunk was shortened before the model was shown it. */
function shortened(fragment: BenchmarkFragment): boolean {
  return typeof fragment.chars === 'number' && fragment.chars > fragment.content.length
}

/** The tooltip on a chunk the ceiling shortened. */
function shortenedWhy(question: Question, fragment: BenchmarkFragment): string {
  const to = question.fragmentMaxChars ?? fragment.content.length
  return `${fragment.chars} characters, cut to ${to} before the prompt.`
}

/**
 * Whether the model was shown this chunk: only the first `context_docs` are
 * mixed in. Null where the run did not record the number.
 */
function wentIntoPrompt(question: Question, index: number): boolean | null {
  if (question.contextDocs === null) return null
  return index < question.contextDocs
}

/**
 * Whether the chunk this question grew from reached the model — three
 * answers, not two: the search returns `retrieval_top_k`, the prompt takes
 * `context_docs`, and a chunk past that cut is neither a hit nor a miss.
 */
function goldShown(question: Question): boolean | null {
  if (!question.retrievalHit || question.contextDocs === null) return null
  return (question.retrievalRank ?? 0) <= question.contextDocs
}

function goldWords(question: Question): string {
  if (!question.retrievalHit) return 'source chunk missed'
  return goldShown(question) === false
    ? `source chunk #${question.retrievalRank}, not shown`
    : `source chunk #${question.retrievalRank}`
}

function goldTone(question: Question): string {
  if (!question.retrievalHit) return 'bg-destructive/10 text-destructive'
  if (goldShown(question) === false)
    return 'bg-warning/15 text-warning-foreground dark:text-warning'
  return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
}

function goldWhy(question: Question): string {
  if (!question.retrievalHit) {
    return 'The chunk this question was written from was not returned.'
  }
  if (goldShown(question) === false) {
    return `Returned, but only the first ${question.contextDocs} went into the prompt.`
  }
  return 'Returned, and it went into the prompt.'
}
</script>

<template>
  <div class="space-y-3">
    <p class="text-xs text-muted-foreground">
      {{ questionCount }} question(s) · {{ answerCount }} answer(s)
      <span v-if="truncated">— showing the first {{ items.length }} verdicts</span>
    </p>
    <p v-if="loading && items.length === 0" class="text-sm text-muted-foreground">Loading…</p>
    <p v-else-if="items.length === 0" class="text-sm text-muted-foreground">Nothing here yet.</p>

    <div v-else class="space-y-1.5">
      <div
        v-for="group in groups"
        :key="group.generator"
        class="rounded-md border border-border/60"
      >
        <button
          type="button"
          class="w-full flex items-center gap-1.5 p-2 text-left cursor-pointer"
          @click="toggle(group.generator)"
        >
          <ChevronRight
            class="h-3.5 w-3.5 shrink-0 transition-transform"
            :class="{ 'rotate-90': openGroups[group.generator] }"
          />
          <span class="text-sm font-medium text-foreground">
            {{ generatorLabel(group.generator) }}
          </span>
          <span class="text-xs text-muted-foreground">{{ group.questions.length }}</span>

          <!-- How it went, before it is opened: which of ten rows is worth
               opening is otherwise invisible until each one has been. Fixed
               widths throughout, so the same figure sits at the same place on
               every row and the rows can be read down rather than one by one. -->
          <span class="ml-auto hidden md:flex shrink-0 items-start gap-8">
            <span v-for="side in group.summary" :key="side.arm" class="w-[21rem]">
              <span class="block text-xs text-muted-foreground" :title="armWords(side.arm)">
                {{ armTileWords(side.arm) }}
              </span>
              <span class="mt-1 flex flex-wrap items-center gap-1">
                <span
                  v-for="part in side.shares"
                  :key="part.verdict"
                  class="rounded px-1.5 py-0.5 text-[11px] whitespace-nowrap"
                  :class="verdictTone(part.verdict)"
                >
                  {{ part.verdict }} {{ share(part.share) }}
                </span>
                <span
                  v-if="side.technical"
                  class="rounded bg-muted px-1.5 py-0.5 text-[11px] whitespace-nowrap text-muted-foreground"
                  title="Calls that did not happen. Out of the shares above."
                >
                  {{ side.technical }} not measured
                </span>
              </span>
            </span>
          </span>
        </button>

        <ul
          v-if="openGroups[group.generator]"
          class="border-t border-border/60 divide-y divide-border/60"
        >
          <li
            v-for="question in group.questions"
            :key="question.key"
            class="bg-muted/60 p-2.5 space-y-2"
          >
            <!-- Written once: every tile below is an answer to this. The band
                 is grey and the tiles on it are not — the question belongs to
                 the row, an answer to one model and one arm. -->
            <div class="flex gap-2 text-sm">
              <span class="font-semibold text-foreground shrink-0">Question:</span>
              <ClampText :text="question.question" :lines="3" />
            </div>

            <!-- What the search found, once for the row: the same chunks go
                 to every arm that searches and every model under test. -->
            <div v-if="question.retrieved">
              <button
                type="button"
                class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                @click="toggleContext(question)"
              >
                <ChevronRight
                  class="h-3 w-3 shrink-0 transition-transform"
                  :class="{ 'rotate-90': openContext[question.key] }"
                />
                <span class="font-medium">Retrieved</span>
                <span
                  class="rounded px-1.5 py-0.5"
                  :class="goldTone(question)"
                  :title="goldWhy(question)"
                >
                  {{ goldWords(question) }}
                </span>
              </button>

              <div v-if="openContext[question.key]" class="mt-1.5 pl-[1.125rem]">
                <p v-if="detailBusy[question.key]" class="text-xs text-muted-foreground">
                  Loading…
                </p>
                <p v-else-if="!fragmentsOf(question).length" class="text-xs text-muted-foreground">
                  Not kept: this run measured with its audit log off.
                </p>
                <ol v-else class="space-y-1.5">
                  <!-- Everything found is kept; only the top of it reached
                       the model. The rest are dimmed, not hidden. -->
                  <li
                    v-for="(fragment, index) in fragmentsOf(question)"
                    :key="index"
                    class="rounded-md border border-border/60 bg-card p-2 text-xs"
                    :class="wentIntoPrompt(question, index) === false ? 'opacity-55' : ''"
                  >
                    <p class="flex flex-wrap items-center gap-2">
                      <span class="font-semibold text-foreground">{{ index + 1 }}</span>
                      <span class="truncate text-muted-foreground">
                        {{ fragment.file_name || 'unnamed' }}
                      </span>
                      <Badge
                        v-if="question.retrievalRank === index + 1"
                        variant="secondary"
                        class="font-normal bg-lime-300 text-lime-950 dark:bg-lime-400"
                        title="The question was written from this chunk."
                      >
                        source
                      </Badge>
                      <Badge
                        v-if="wentIntoPrompt(question, index) === false"
                        variant="outline"
                        class="font-normal"
                        :title="`Past the first ${question.contextDocs}; not put in the prompt.`"
                      >
                        not shown
                      </Badge>
                      <Badge
                        v-if="shortened(fragment)"
                        variant="outline"
                        class="font-normal"
                        :title="shortenedWhy(question, fragment)"
                      >
                        cut
                      </Badge>
                      <span class="ml-auto shrink-0 text-muted-foreground" title="Similarity">
                        {{ fragment.score }}
                      </span>
                    </p>
                    <ClampText :text="fragment.content" :lines="3" class="mt-1 text-foreground" />
                  </li>
                </ol>
              </div>
            </div>

            <!-- One row per model, one column per arm. -->
            <div v-for="row in question.models" :key="row.model" class="pl-3 space-y-2">
              <div class="grid grid-cols-1 gap-2" :class="columnsFor(question.arms.length)">
                <template v-for="(tile, index) in row.tiles" :key="question.arms[index]">
                  <div
                    v-if="tile"
                    class="rounded-md border border-border/60 bg-card p-2.5 space-y-2"
                  >
                    <div class="flex items-start gap-2">
                      <span
                        class="text-xs font-medium text-muted-foreground"
                        :title="armWords(tile.contextMode)"
                      >
                        {{ armTileWords(tile.contextMode) }}
                      </span>
                      <ModelChip :name="tile.model" class="ml-auto" />
                    </div>

                    <!-- The one figure in the tile everything else explains, so
                         it is read before any of them rather than found among
                         them. -->
                    <div class="flex items-center gap-2 text-base">
                      <span class="font-semibold text-foreground">Verdict:</span>
                      <span
                        class="inline-flex items-center gap-1 rounded px-2 py-1 text-base font-semibold"
                        :class="verdictTone(tile.verdict)"
                        :title="tile.verdict === TECHNICAL ? technicalWhy(tile) : undefined"
                      >
                        <UserRound v-if="tile.overrideId" class="h-4 w-4" />
                        {{ tile.verdict }}
                        <!-- On the verdict: the answer was cut off and graded
                             anyway, so the verdict covers part of a sentence. -->
                        <AlertTriangle
                          v-if="tile.call?.truncated"
                          class="h-4 w-4 text-warning"
                          :title="cutOffWhy(tile.call)"
                        />
                      </span>
                      <span class="ml-auto flex shrink-0 items-center gap-0.5">
                        <Button
                          v-if="tile.overrideId"
                          variant="ghost"
                          size="icon"
                          class="h-6 w-6 text-muted-foreground hover:text-foreground"
                          title="Take my verdict back"
                          :disabled="busyKey === tile.key"
                          @click="undo(tile)"
                        >
                          <RotateCcw class="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          class="h-6 w-6 text-muted-foreground hover:text-emerald-600"
                          title="Mark correct"
                          :disabled="busyKey === tile.key"
                          @click="override(tile, 'correct')"
                        >
                          <Check class="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          class="h-6 w-6 text-muted-foreground hover:text-destructive"
                          title="Mark hallucination"
                          :disabled="busyKey === tile.key"
                          @click="override(tile, 'hallucinate')"
                        >
                          <X class="h-3.5 w-3.5" />
                        </Button>
                      </span>
                    </div>

                    <div class="text-sm">
                      <span class="font-semibold text-foreground">Answer:</span>
                      <button
                        type="button"
                        class="ml-2 text-xs text-muted-foreground underline decoration-dotted hover:text-foreground cursor-pointer"
                        @click="showPrompt(tile)"
                      >
                        See what was sent
                      </button>
                      <ClampText :text="tile.answer" :lines="5" class="text-foreground" />
                    </div>

                    <div class="text-sm">
                      <span class="font-semibold text-foreground">Judges:</span>
                      <table class="w-full mt-1 text-xs">
                        <thead>
                          <tr class="text-muted-foreground">
                            <th class="w-px" />
                            <th
                              v-for="block in tile.blocks"
                              :key="block"
                              class="px-1 py-0.5 font-normal text-center"
                              :title="blockWords(block)"
                            >
                              {{ blockCode(block) }}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="judge in tile.judges" :key="judge.name" class="align-middle">
                            <td class="py-0.5 pr-2">
                              <Badge
                                v-if="judge.name === OWNER"
                                variant="secondary"
                                class="font-normal"
                              >
                                owner
                              </Badge>
                              <ModelChip v-else :name="judge.name" />
                            </td>
                            <td
                              v-for="cell in judge.cells"
                              :key="cell.block"
                              class="px-1 py-0.5 text-center"
                            >
                              <!-- Nothing from this grader on this check: it was
                                   recused, or the check ran without it. -->
                              <span
                                v-if="!cell.row"
                                class="text-muted-foreground"
                                title="No verdict from this grader"
                              >
                                ×
                              </span>

                              <!-- Asked once: the verdict, and why on hover. -->
                              <span
                                v-else-if="cell.block === 'direct'"
                                class="rounded px-1.5 py-0.5"
                                :class="verdictTone(cell.row.verdict)"
                                :title="cell.row.reasoning"
                              >
                                {{ cell.row.verdict }}
                              </span>

                              <!-- Pushed back on: how much it took, and the
                                   exchange itself — an argument reads as an
                                   argument, and the turn it lost is the one
                                   that changes colour. -->
                              <template v-else-if="cell.row.denial">
                                <HoverPanel v-if="cell.row.denial.log.length">
                                  <template #trigger>
                                    <span class="cursor-help underline decoration-dotted">
                                      {{ heldRounds(cell.row) }}
                                    </span>
                                  </template>
                                  <p class="font-medium text-foreground mb-2">
                                    {{ cell.row.denial.flipped ? 'Gave in' : 'Held out' }}
                                  </p>
                                  <ul class="space-y-2">
                                    <li
                                      v-for="round in cell.row.denial.log"
                                      :key="round.round"
                                      class="space-y-1"
                                    >
                                      <p class="text-muted-foreground italic">
                                        {{ round.objection }}
                                      </p>
                                      <p
                                        class="whitespace-pre-wrap break-words rounded px-1.5 py-1"
                                        :class="
                                          heldAt(cell.row, round.round)
                                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                                            : 'bg-destructive/10 text-destructive'
                                        "
                                      >
                                        {{ round.answer }}
                                      </p>
                                    </li>
                                  </ul>
                                </HoverPanel>
                                <span v-else :title="cell.row.denial.note">
                                  {{ heldRounds(cell.row) }}
                                </span>
                              </template>

                              <!-- Repeated: the share that came back right, and
                                   every repeat behind it. -->
                              <template v-else-if="cell.row.repeats">
                                <HoverPanel v-if="cell.row.repeats.log.length">
                                  <template #trigger>
                                    <span class="cursor-help underline decoration-dotted">
                                      {{ share(cell.row.repeats.accuracy) }}
                                    </span>
                                  </template>
                                  <p class="font-medium text-foreground mb-2">
                                    {{ share(cell.row.repeats.consistency) }} of the repeats said
                                    the same thing
                                  </p>
                                  <ul class="space-y-2">
                                    <li v-for="trial in cell.row.repeats.log" :key="trial.trial">
                                      <p class="text-muted-foreground">
                                        Trial {{ trial.trial }}, t {{ trial.temperature }} —
                                        {{ trial.correct ? 'correct' : 'not' }}
                                      </p>
                                      <p
                                        class="whitespace-pre-wrap break-words rounded px-1.5 py-1"
                                        :class="
                                          trial.correct
                                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                                            : 'bg-destructive/10 text-destructive'
                                        "
                                      >
                                        {{ trial.answer }}
                                      </p>
                                    </li>
                                  </ul>
                                </HoverPanel>
                                <span v-else :title="cell.row.repeats.note">
                                  {{ share(cell.row.repeats.accuracy) }}
                                </span>
                              </template>

                              <span
                                v-else
                                class="text-muted-foreground"
                                :title="emptyWhy(cell.block)"
                              >
                                —
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div v-else />
                </template>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>

    <!-- The exchange behind one tile. A dialog, not a panel in the tile: in
         the grid a prompt would push the arm it is compared against off. -->
    <Dialog
      :open="promptFor !== null"
      @update:open="
        (open: boolean) => {
          if (!open) promptFor = null
        }
      "
    >
      <DialogScrollContent class="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>What was sent</DialogTitle>
          <DialogDescription v-if="promptFor">
            {{ armWords(promptFor.contextMode) }} · {{ shortModel(promptFor.model) }}
          </DialogDescription>
        </DialogHeader>

        <p v-if="!promptPanel" class="text-sm text-muted-foreground">Loading…</p>
        <div v-else class="space-y-5">
          <section>
            <h3 class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              To the model
            </h3>
            <p v-if="!promptPanel.answerer" class="mt-1.5 text-sm text-muted-foreground">
              Nothing was kept: this run measured with its audit log off.
            </p>
            <template v-else>
              <details v-if="promptPanel.answerer.responder_system" class="mt-1.5">
                <summary class="cursor-pointer text-xs text-muted-foreground">
                  System prompt
                </summary>
                <pre
                  class="mt-1 whitespace-pre-wrap break-words rounded-md border border-border/60 bg-muted/50 p-2 text-xs text-foreground"
                  >{{ promptPanel.answerer.responder_system }}</pre
                >
              </details>
              <p
                class="mt-2 text-xs text-muted-foreground"
                :title="
                  promptPanel.answerer.context ? 'Highlighted: what the search put in.' : undefined
                "
              >
                Prompt
              </p>
              <pre
                class="mt-1 whitespace-pre-wrap break-words rounded-md border border-border/60 bg-muted/50 p-2 text-xs text-foreground"
              ><span
                  v-for="(part, index) in promptParts(promptPanel.answerer)"
                  :key="index"
                  :class="part.fromData ? 'rounded bg-lime-200/70 dark:bg-lime-400/25' : ''"
                >{{ part.text }}</span></pre>
              <template v-if="strayContext(promptPanel.answerer)">
                <p
                  class="mt-2 text-xs text-muted-foreground"
                  title="Shown separately: the prompt above was cut before this ended."
                >
                  What the search put in
                </p>
                <pre
                  class="mt-1 whitespace-pre-wrap break-words rounded-md border border-border/60 bg-lime-200/40 dark:bg-lime-400/15 p-2 text-xs text-foreground"
                  >{{ strayContext(promptPanel.answerer) }}</pre
                >
              </template>
            </template>
          </section>

          <section v-for="judge in promptPanel.judges" :key="judge.key">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              To {{ judgeWords(judge.name) }} · {{ blockWords(judge.block) }}
            </h3>
            <p
              v-if="judge.none"
              class="mt-1.5 text-sm text-muted-foreground"
              title="An option letter matched, or an abstention recognised by its wording."
            >
              No judge was asked: the verdict cost no call.
            </p>
            <template v-else>
              <details v-if="judge.system" class="mt-1.5">
                <summary class="cursor-pointer text-xs text-muted-foreground">
                  System prompt
                </summary>
                <pre
                  class="mt-1 whitespace-pre-wrap break-words rounded-md border border-border/60 bg-muted/50 p-2 text-xs text-foreground"
                  >{{ judge.system }}</pre
                >
              </details>
              <p class="mt-2 text-xs text-muted-foreground">Prompt</p>
              <pre
                class="mt-1 whitespace-pre-wrap break-words rounded-md border border-border/60 bg-muted/50 p-2 text-xs text-foreground"
                >{{ judge.prompt }}</pre
              >
              <p
                v-if="judge.raw"
                class="mt-2 text-xs text-muted-foreground"
                title="Before parsing: the text the verdict was read from."
              >
                Reply
              </p>
              <pre
                v-if="judge.raw"
                class="mt-1 whitespace-pre-wrap break-words rounded-md border border-border/60 bg-card p-2 text-xs text-foreground"
                >{{ judge.raw }}</pre
              >
            </template>
          </section>

          <p
            v-if="promptPanel.answerer && !promptPanel.judges.length"
            class="text-sm text-muted-foreground"
          >
            No judging was kept for this answer.
          </p>
        </div>
      </DialogScrollContent>
    </Dialog>
  </div>
</template>
