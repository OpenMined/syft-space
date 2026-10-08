<template>
  <section class="space-y-6" data-testid="screen-QuestionsPage">
    <div class="space-y-0.5">
      <h1 class="heading-3">Every question and answer</h1>
      <p class="text-sm text-muted-foreground" data-testid="questions-subtitle">{{ subtitle }}</p>
    </div>

    <div class="flex flex-wrap gap-2" role="group" aria-label="Filter by outcome">
      <Button
        v-for="chip in chips"
        :key="chip.key"
        size="sm"
        :variant="group === chip.key ? 'default' : 'outline'"
        :aria-pressed="group === chip.key"
        :data-testid="`group-${chip.key}`"
        @click="group = chip.key"
      >
        {{ chip.label }} · {{ chip.count }}
      </Button>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="max-w-full space-y-1.5">
        <Label for="questions-kind" class="text-xs text-muted-foreground">Kind of question</Label>
        <Select v-model="kind">
          <SelectTrigger id="questions-kind" class="w-56 max-w-full" data-testid="kind-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All kinds</SelectItem>
            <SelectItem v-for="k in kinds" :key="k" :value="k">{{ kindLabel(k) }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div class="min-w-0 flex-[1_1_280px] space-y-1.5">
        <Label for="questions-search" class="text-xs text-muted-foreground">Search questions</Label>
        <Input
          id="questions-search"
          v-model="search"
          type="search"
          placeholder="A name, a number, an article…"
          data-testid="questions-search"
        />
      </div>
    </div>

    <Alert v-if="listError" variant="destructive" data-testid="questions-error">
      <AlertDescription class="flex flex-wrap items-center justify-between gap-3">
        <span>{{ listError }}</span>
        <Button variant="outline" size="sm" @click="fetchPage">Try again</Button>
      </AlertDescription>
    </Alert>

    <div
      class="overflow-x-auto rounded-lg border border-border bg-card text-sm"
      :aria-busy="listLoading"
    >
      <div
        class="flex min-w-[680px] items-center gap-4 border-b border-border bg-muted/40 px-4 py-2.5 text-xs font-medium text-muted-foreground"
      >
        <span class="w-7 shrink-0">#</span>
        <span class="flex-[1_1_420px]">Question</span>
        <span class="w-[110px] shrink-0">On its own</span>
        <span class="w-[110px] shrink-0">With your data</span>
        <span class="w-[18px] shrink-0" />
      </div>

      <div
        v-for="q in rows"
        :key="q.qa_id"
        class="border-b border-border last:border-b-0"
        data-testid="question-row"
      >
        <button
          type="button"
          class="flex w-full min-w-[680px] items-center gap-4 px-4 py-3 text-left hover:bg-muted/40 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          :class="openId === q.qa_id && 'bg-muted/40'"
          :aria-expanded="openId === q.qa_id"
          :aria-controls="`question-${q.qa_id}`"
          @click="toggle(q.qa_id)"
        >
          <span class="w-7 shrink-0 text-muted-foreground tabular-nums">{{ q.n }}</span>
          <span class="flex min-w-0 flex-[1_1_420px] flex-col gap-0.5">
            <span class="break-words">{{ q.question }}</span>
            <span class="text-xs text-muted-foreground"
              >{{ kindLabel(q.generator) }} · {{ articleOf(q) }}</span
            >
          </span>
          <span class="w-[110px] shrink-0" data-testid="verdict-closed">
            <VerdictPill :verdict="q.verdict_alone" :generator="q.generator" />
          </span>
          <span class="w-[110px] shrink-0" data-testid="verdict-ctx">
            <VerdictPill :verdict="q.verdict_with" :generator="q.generator" />
          </span>
          <ChevronDown
            class="size-[18px] shrink-0 text-muted-foreground transition-transform"
            :class="openId === q.qa_id && 'rotate-180'"
            aria-hidden="true"
          />
        </button>

        <div
          v-if="openId === q.qa_id"
          :id="`question-${q.qa_id}`"
          class="flex flex-col gap-4 px-4 pt-1 pb-[18px] md:pl-[60px]"
          data-testid="question-detail"
        >
          <div class="flex flex-col gap-0.5">
            <span class="text-xs text-muted-foreground"
              >Correct answer, from “{{ articleOf(q) }}”</span
            >
            <b class="font-semibold break-words" data-testid="gold-answer">{{
              sentence(q.gold_answer)
            }}</b>
          </div>

          <p v-if="detailError" class="text-sm text-destructive">{{ detailError }}</p>
          <div v-else-if="!detail" aria-busy="true" data-testid="question-detail-loading">
            <span class="sr-only">Loading this question</span>
            <Skeleton class="h-40" />
          </div>
          <div
            v-else
            class="overflow-hidden rounded-md border border-border bg-background"
            data-testid="detail-grid"
          >
            <div
              :class="GRID_ROW"
              class="border-border bg-muted/40 text-xs font-medium text-muted-foreground"
            >
              <span />
              <span>On its own</span>
              <span>With your data</span>
            </div>

            <div :class="GRID_ROW" data-testid="row-given">
              <span class="text-muted-foreground">What it was given</span>
              <span class="text-muted-foreground">{{ DASH }}</span>
              <span>
                <span v-if="fragmentsError" class="text-muted-foreground">{{
                  fragmentsError
                }}</span>
                <Skeleton v-else-if="fragments === null" class="h-10" />
                <button
                  v-else-if="fragments.length"
                  type="button"
                  class="flex w-full flex-col items-start gap-1 text-left focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                  aria-haspopup="dialog"
                  data-testid="read-full-text"
                  @click="excerptOpen = true"
                >
                  <span class="line-clamp-2 break-words text-foreground/80">{{
                    fragments[0]!.content
                  }}</span>
                  <span class="text-xs font-medium text-primary">Read the full text</span>
                </button>
                <span v-else class="text-muted-foreground">{{ DASH }}</span>
              </span>
            </div>

            <div :class="GRID_ROW" data-testid="row-answer">
              <span class="text-muted-foreground">Model’s answer</span>
              <span
                v-for="arm in ARMS"
                :key="arm"
                class="flex flex-col items-start gap-1 break-words"
                :data-testid="`answer-${arm}`"
              >
                <span>{{ armOf(detail, arm)?.answer || DASH }}</span>
                <span
                  v-if="armOf(detail, arm)?.web_search_unused"
                  class="rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
                  title="Asked to search the web, but cited nothing."
                  data-testid="searched-no"
                  >Searched: no</span
                >
                <span
                  v-if="armOf(detail, arm)?.citations?.length"
                  class="flex flex-wrap gap-x-2 gap-y-0.5 text-xs"
                  data-testid="citations"
                >
                  <a
                    v-for="(cite, n) in armOf(detail, arm)!.citations"
                    :key="`${n}-${cite.url}`"
                    :href="safeUrl(cite.url)"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="max-w-60 truncate text-primary hover:underline"
                    :title="cite.url"
                    >{{ cite.title || hostOf(cite.url) }}</a
                  >
                </span>
              </span>
            </div>

            <div
              v-for="(judge, i) in judges"
              :key="judge.model"
              :class="GRID_ROW"
              data-testid="row-judge"
            >
              <span class="flex flex-col gap-0.5">
                <b class="font-semibold">Judge {{ i + 1 }}</b>
                <span class="text-xs text-muted-foreground">{{ modelName(judge.model) }}</span>
              </span>
              <span
                v-for="arm in ARMS"
                :key="arm"
                class="flex flex-col items-start gap-1 break-words text-foreground/80"
                :data-testid="`judge-${arm}`"
              >
                <template v-if="judge[ARM_KEY[arm]]">
                  <VerdictPill
                    :verdict="judge[ARM_KEY[arm]]"
                    :generator="q.generator"
                    :behavior="judgeBehavior(judge, arm)"
                  />
                  <span v-if="judgeReasoning(judge, arm)">{{ judgeReasoning(judge, arm) }}</span>
                </template>
                <template v-else>{{ DASH }}</template>
              </span>
            </div>

            <div :class="GRID_ROW" data-testid="row-held">
              <span class="flex flex-col gap-0.5">
                <span class="text-muted-foreground">Held when challenged</span>
                <span class="text-[11px] leading-snug text-muted-foreground"
                  >Rounds held. Only right answers are challenged.</span
                >
              </span>
              <b v-for="arm in ARMS" :key="arm" class="font-semibold tabular-nums">{{
                heldText(detail, arm)
              }}</b>
            </div>

            <div :class="GRID_ROW" class="border-b-0" data-testid="row-repeats">
              <span class="flex flex-col gap-0.5">
                <span class="text-muted-foreground">Right when asked again</span>
                <span v-if="trials(detail)" class="text-[11px] leading-snug text-muted-foreground"
                  >Out of {{ trials(detail) }} repeats</span
                >
              </span>
              <b v-for="arm in ARMS" :key="arm" class="font-semibold tabular-nums">{{
                repeatText(detail, arm)
              }}</b>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="listLoading && !pageData"
        class="space-y-3 p-4"
        aria-busy="true"
        data-testid="questions-loading"
      >
        <span class="sr-only">Loading questions</span>
        <Skeleton v-for="n in 3" :key="n" class="h-10" />
      </div>
      <p
        v-else-if="pageData && !rows.length"
        class="p-4 text-muted-foreground"
        data-testid="questions-empty"
      >
        No questions match these filters. Clear a filter or the search to see more.
      </p>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <span class="text-sm text-muted-foreground tabular-nums" data-testid="question-range"
        >Showing {{ range }} of {{ total }} questions</span
      >
      <span class="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          :disabled="page === 0"
          data-testid="prev-page"
          @click="page -= 1"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="page >= pages - 1"
          data-testid="next-page"
          @click="page += 1"
        >
          Next
        </Button>
      </span>
    </div>

    <Dialog v-model:open="excerptOpen">
      <DialogContent class="flex max-h-[80vh] flex-col gap-0 p-0 sm:max-w-[720px]">
        <DialogHeader class="gap-0.5 border-b border-border py-4 pr-14 pl-5 text-left">
          <DialogTitle>What the model was given</DialogTitle>
          <DialogDescription class="text-xs">{{ openRow?.question }}</DialogDescription>
        </DialogHeader>
        <div class="overflow-y-auto px-5 pt-1 pb-5" data-testid="excerpts">
          <p v-if="!fragments?.length" class="py-3.5 text-sm text-muted-foreground">
            Nothing was sent with this question.
          </p>
          <div
            v-for="(fragment, i) in fragments ?? []"
            :key="i"
            class="flex flex-col gap-1.5 border-b border-border py-3.5 last:border-b-0"
            data-testid="excerpt"
          >
            <span class="text-xs text-muted-foreground"
              >From “{{ fragment.document_title || fragment.file_name }}”</span
            >
            <p class="text-sm leading-relaxed whitespace-pre-line">{{ fragment.content }}</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import {
  computed,
  defineComponent,
  h,
  onBeforeUnmount,
  ref,
  shallowRef,
  watch,
  type PropType,
} from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import type {
  BenchmarkQuestionDetail,
  BenchmarkQuestionJudge,
  BenchmarkQuestionPage,
  BenchmarkQuestionRow,
  BenchmarkReportFragment,
} from '@/api/types'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorDetail } from '@/lib/errors'
import { cn } from '@/lib/utils'
import { useReport, useRun } from './context'
import { DASH } from './figures'
import {
  GROUP_LABEL,
  KIND_LABEL,
  VERDICT_COLORS,
  kindLabel,
  modelName,
  outcomeLabel,
  verdictTip,
} from './labels'
import { heldOf, isTrick } from './selectors'
import { sortKinds, sortQuestions } from '../questionOrder'
import { ARM_KEY, type Arm, type Group } from './types'

const PAGE_SIZE = 25
const SEARCH_DEBOUNCE_MS = 300

type GroupFilter = Group | 'all'
const GROUPS: Group[] = ['fixed', 'either', 'still', 'worse']
const ARMS: Arm[] = ['closed', 'ctx']
const GRID_ROW =
  'grid grid-cols-[120px_minmax(0,1fr)_minmax(0,1fr)] gap-4 border-b border-border/60 px-3 py-2.5 md:grid-cols-[180px_minmax(0,1fr)_minmax(0,1fr)]'

const VerdictPill = defineComponent({
  props: {
    verdict: { type: String as PropType<string | null>, default: null },
    /** Control kinds show the fine outcome. */
    generator: { type: String as PropType<string | null>, default: null },
    behavior: { type: String as PropType<string | null>, default: null },
  },
  setup(props) {
    return () =>
      props.verdict
        ? h(
            'span',
            {
              class: cn(
                'inline-block rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap',
                VERDICT_COLORS[props.verdict] ?? 'bg-muted text-muted-foreground',
              ),
              title: verdictTip(props.verdict) || undefined,
              'data-verdict': props.verdict,
            },
            outcomeLabel(props.generator, props.verdict, props.behavior),
          )
        : h('span', { class: 'text-muted-foreground' }, DASH)
  },
})

const report = useReport()
const run = useRun()

const group = ref<GroupFilter>('all')
const kind = ref('all')
const search = ref('')
const query = ref('')
const page = ref(0)
const openId = ref<string | null>(null)

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (text) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (query.value = text.trim()), SEARCH_DEBOUNCE_MS)
})
onBeforeUnmount(() => clearTimeout(searchTimer))

// --- the page of questions ------------------------------------------------------

const pageData = shallowRef<BenchmarkQuestionPage | null>(null)
const listLoading = ref(false)
const listError = ref<string | null>(null)
let listRequest = 0

async function fetchPage(): Promise<void> {
  const model = run.model.value
  if (!model) return
  const request = ++listRequest
  listLoading.value = true
  listError.value = null
  try {
    const result = await report.loadQuestions(run.jobId, {
      model,
      group: group.value === 'all' ? undefined : group.value,
      generator: kind.value === 'all' ? undefined : kind.value,
      q: query.value || undefined,
      excluded: 'hide',
      limit: PAGE_SIZE,
      offset: page.value * PAGE_SIZE,
    })
    if (request !== listRequest) return
    pageData.value = result
    if (page.value > 0 && page.value * PAGE_SIZE >= result.total) {
      page.value = Math.max(Math.ceil(result.total / PAGE_SIZE) - 1, 0)
    }
  } catch (e) {
    if (request === listRequest) listError.value = apiErrorDetail(e, 'Could not load the questions')
  } finally {
    if (request === listRequest) listLoading.value = false
  }
}

watch([group, kind, query, () => run.model.value], () => {
  openId.value = null
  if (page.value !== 0) page.value = 0
  else void fetchPage()
})
watch(page, () => {
  openId.value = null
  void fetchPage()
})
watch(
  () => report.revision.value,
  () => {
    void fetchPage()
    if (openId.value) void loadDetail(openId.value)
  },
)
void fetchPage()

const counts = computed(() => pageData.value?.counts ?? null)

const subtitle = computed(() => {
  const model = run.model.value
  const asked = run.modelReport.value?.asked ?? counts.value?.all
  const parts = [model ? modelName(model) : null, asked !== undefined ? `${asked} questions` : null]
  const graders = (run.data.value?.judges ?? []).map((j, i) => `Judge ${i + 1} (${modelName(j)})`)
  const last = graders.pop()
  if (last) parts.push(`graded by ${graders.length ? `${graders.join(', ')} and ${last}` : last}`)
  return parts.filter(Boolean).join(' · ')
})

/** The run's kinds in the canonical order. */
const kinds = computed(() => {
  const recorded = run.data.value?.method.kinds ?? []
  return sortKinds(recorded.length ? recorded : Object.keys(KIND_LABEL)).filter((k) => !isTrick(k))
})

const chips = computed(() => {
  const c = counts.value
  const fallback = run.modelReport.value
  return [
    { key: 'all' as GroupFilter, label: 'All questions', count: c?.all ?? fallback?.asked ?? 0 },
    ...GROUPS.map((g) => ({
      key: g as GroupFilter,
      label: GROUP_LABEL[g],
      count: c?.[g] ?? fallback?.groups[g] ?? 0,
    })),
  ]
})

/** The server's order, kept; kinds never mixed within a page. */
const rows = computed(() =>
  sortQuestions(pageData.value?.items ?? [], (q) => ({ generator: q.generator })),
)
const total = computed(() => pageData.value?.total ?? 0)
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const range = computed(() => {
  const n = total.value
  const from = n ? page.value * PAGE_SIZE + 1 : 0
  return `${from}–${Math.min(n, page.value * PAGE_SIZE + PAGE_SIZE)}`
})

function articleOf(q: BenchmarkQuestionRow): string {
  return q.document_title || q.file_name
}

/** The gold answer as one sentence, with its full stop. */
function sentence(text: string): string {
  const t = text.trim()
  return /[.!?…”"')]$/.test(t) ? t : `${t}.`
}

// --- the open question ----------------------------------------------------------

const openRow = computed(() => rows.value.find((q) => q.qa_id === openId.value) ?? null)
const detail = shallowRef<BenchmarkQuestionDetail | null>(null)
const detailError = ref<string | null>(null)
const fragments = shallowRef<BenchmarkReportFragment[] | null>(null)
const fragmentsError = ref<string | null>(null)
const excerptOpen = ref(false)
let detailRequest = 0

async function loadDetail(qaId: string): Promise<void> {
  const model = run.model.value
  if (!model) return
  const request = ++detailRequest
  detailError.value = null
  fragmentsError.value = null
  report
    .loadFragments(run.jobId, qaId, model)
    .then((list) => {
      if (request === detailRequest) fragments.value = list
    })
    .catch(() => {
      if (request === detailRequest) fragmentsError.value = 'Could not load the passages.'
    })
  try {
    const d = await report.loadQuestion(run.jobId, qaId, model)
    if (request === detailRequest) detail.value = d
  } catch (e) {
    if (request === detailRequest)
      detailError.value = apiErrorDetail(e, 'Could not load this question')
  }
}

function toggle(qaId: string): void {
  openId.value = openId.value === qaId ? null : qaId
}

watch(openId, (id) => {
  detailRequest += 1
  detail.value = null
  fragments.value = null
  excerptOpen.value = false
  if (id) void loadDetail(id)
})

/** Primary first: Judge 1. */
const judges = computed<BenchmarkQuestionJudge[]>(() =>
  [...(detail.value?.judges ?? [])].sort((a, b) => Number(b.primary) - Number(a.primary)),
)

function judgeReasoning(judge: BenchmarkQuestionJudge, arm: Arm): string | null {
  return (arm === 'closed' ? judge.alone_reasoning : judge.with_reasoning) || null
}

function judgeBehavior(judge: BenchmarkQuestionJudge, arm: Arm): string | null {
  return (arm === 'closed' ? judge.alone_behavior : judge.with_behavior) ?? null
}

function armOf(d: BenchmarkQuestionDetail, arm: Arm) {
  return d.arms[ARM_KEY[arm]]
}

/** Only web links; anything else would run in the page. */
function safeUrl(url: string): string | undefined {
  return /^https?:\/\//i.test(url) ? url : undefined
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function heldText(d: BenchmarkQuestionDetail, arm: Arm): string {
  const held = heldOf(armOf(d, arm)?.denial)
  return held ? `${held.held} of ${held.of}` : DASH
}

function repeatText(d: BenchmarkQuestionDetail, arm: Arm): string {
  const repeats = armOf(d, arm)?.repeats
  return repeats?.trials ? `${repeats.right} of ${repeats.trials}` : DASH
}

function trials(d: BenchmarkQuestionDetail): number | null {
  return d.arms.with?.repeats?.trials || d.arms.alone?.repeats?.trials || null
}
</script>
