<template>
  <section id="report-questions" class="space-y-3" data-testid="report-questions">
    <div>
      <h2 class="heading-4">The questions</h2>
      <p class="text-sm text-muted-foreground">
        Results for {{ name }}. Select a question to compare its answers.
      </p>
    </div>

    <template v-if="run.model.value">
      <div class="flex flex-wrap gap-2" role="group" aria-label="Filter by outcome">
        <Button
          v-for="chip in groupChips"
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

      <div v-if="run.kind.value">
        <Button
          size="sm"
          variant="secondary"
          :aria-label="`Clear filter: ${kindLabel(run.kind.value)}`"
          data-testid="kind-chip"
          @click="run.setKind(null)"
        >
          {{ kindLabel(run.kind.value) }}
          <X />
        </Button>
      </div>

      <Alert v-if="listError" variant="destructive" data-testid="questions-error">
        <AlertDescription class="flex flex-wrap items-center justify-between gap-3">
          <span>{{ listError }}</span>
          <Button variant="outline" size="sm" @click="fetchPage">Try again</Button>
        </AlertDescription>
      </Alert>

      <p v-if="pageData" class="text-xs text-muted-foreground" data-testid="question-range">
        Showing {{ range }} of {{ pageData.total }} questions
      </p>

      <div class="divide-y rounded-lg border bg-card" :aria-busy="listLoading">
        <div v-for="q in shown" :key="q.qa_id" data-testid="question-row">
          <button
            type="button"
            class="flex w-full flex-col gap-3 px-4 py-3 text-left hover:bg-accent/50 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none sm:flex-row sm:items-center"
            :aria-expanded="openId === q.qa_id"
            :aria-controls="`question-${q.qa_id}`"
            @click="toggle(q.qa_id)"
          >
            <span class="min-w-0 flex-1">
              <span class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span>{{ kindLabel(q.generator) }} · {{ articleOf(q) }}</span>
                <Badge
                  v-if="q.excluded"
                  variant="outline"
                  class="border-transparent bg-muted text-muted-foreground"
                  data-testid="excluded-badge"
                >
                  Excluded
                </Badge>
              </span>
              <span
                class="mt-0.5 block text-sm break-words"
                :class="q.excluded && 'text-muted-foreground'"
                >{{ q.question }}</span
              >
            </span>
            <span class="flex shrink-0 items-center gap-4">
              <span v-for="arm in ARMS" :key="arm" class="w-28">
                <span class="block text-xs text-muted-foreground">{{ ARM_SHORT[arm] }}</span>
                <Badge
                  variant="outline"
                  class="mt-1"
                  :class="verdictClass(rowVerdict(q, arm))"
                  :data-testid="`verdict-${arm}`"
                >
                  {{ rowVerdict(q, arm) ? verdictLabel(rowVerdict(q, arm)!) : '—' }}
                </Badge>
              </span>
              <ChevronDown
                class="ml-auto size-4 text-muted-foreground transition-transform"
                :class="openId === q.qa_id && 'rotate-180'"
                aria-hidden="true"
              />
            </span>
          </button>

          <div
            v-if="openId === q.qa_id"
            :id="`question-${q.qa_id}`"
            class="space-y-4 px-4 pb-4"
            data-testid="question-detail"
          >
            <p v-if="detailError" class="text-sm text-destructive">{{ detailError }}</p>
            <div
              v-else-if="!detail"
              class="space-y-2"
              aria-busy="true"
              data-testid="question-detail-loading"
            >
              <span class="sr-only">Loading this question</span>
              <Skeleton class="h-24" />
            </div>
            <template v-else>
              <div class="grid grid-cols-1 gap-3 *:min-w-0 *:break-words md:grid-cols-3">
                <div class="rounded-lg border p-3">
                  <p class="text-xs text-muted-foreground">Correct answer, from your reporting</p>
                  <p class="mt-2 text-sm">{{ detail.question.gold_answer }}</p>
                  <Button
                    variant="link"
                    size="sm"
                    class="mt-1 h-auto px-0"
                    aria-haspopup="dialog"
                    data-testid="show-source"
                    @click="openExcerpt(detail)"
                  >
                    Show source paragraph
                  </Button>
                </div>
                <div v-for="arm in ARMS" :key="arm" class="rounded-lg border p-3">
                  <div class="flex items-start justify-between gap-2">
                    <p class="text-xs text-muted-foreground">{{ ARM_LABEL[arm] }}</p>
                    <Badge
                      v-if="armOf(detail, arm)"
                      variant="outline"
                      :class="verdictClass(armOf(detail, arm)!.verdict)"
                    >
                      {{ verdictLabel(armOf(detail, arm)!.verdict) }}
                    </Badge>
                  </div>
                  <p v-if="armOf(detail, arm)?.answer" class="mt-2 text-sm">
                    “{{ armOf(detail, arm)!.answer }}”
                  </p>
                  <p v-else class="mt-2 text-sm text-muted-foreground">No answer recorded.</p>
                  <p v-if="armOf(detail, arm)?.override" class="mt-2 text-xs text-muted-foreground">
                    Verdict changed by you
                  </p>
                  <p
                    v-if="arm === 'ctx' && retrievalText(detail)"
                    class="mt-2 text-xs text-muted-foreground"
                    data-testid="retrieval"
                  >
                    {{ retrievalText(detail) }}
                  </p>
                </div>
              </div>

              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b text-left text-xs text-muted-foreground">
                      <th class="py-2 pr-4 font-normal">Judge</th>
                      <th class="w-24 py-2 pr-4 font-normal sm:w-32">On its own</th>
                      <th class="w-24 py-2 font-normal sm:w-32">With your data</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y">
                    <tr v-for="judge in detail.judges" :key="judge.model">
                      <td class="py-2 pr-4">{{ modelName(judge.model) }}</td>
                      <td class="py-2 pr-4">{{ judgeVerdict(judge.alone) }}</td>
                      <td class="py-2">{{ judgeVerdict(judge.with) }}</td>
                    </tr>
                    <tr v-if="hasHeld(detail)">
                      <td class="py-2 pr-4">
                        <span class="inline-flex items-center gap-1.5 text-muted-foreground">
                          Held when challenged
                          <InfoTip text="Rounds held. Only right answers are challenged." />
                        </span>
                      </td>
                      <td class="py-2 pr-4">{{ heldText(detail, 'closed') }}</td>
                      <td class="py-2">{{ heldText(detail, 'ctx') }}</td>
                    </tr>
                    <tr v-if="hasRepeats(detail)">
                      <td class="py-2 pr-4">
                        <span class="inline-flex items-center gap-1.5 text-muted-foreground">
                          Right when asked again
                          <InfoTip text="Repeats that were right, out of all repeats." />
                        </span>
                      </td>
                      <td class="py-2 pr-4">{{ repeatText(detail, 'closed') }}</td>
                      <td class="py-2">{{ repeatText(detail, 'ctx') }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-if="detail.judges_agreed !== null" class="mt-2 text-xs text-muted-foreground">
                  {{ detail.judges_agreed ? 'All judges agreed.' : 'Judges disagreed.' }}
                </p>
              </div>

              <div class="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="!detail.arms.alone && !detail.arms.with"
                  data-testid="change-verdict"
                  @click="openOverride(detail)"
                >
                  Change a verdict
                </Button>
                <Button
                  v-if="detail.question.excluded"
                  variant="outline"
                  size="sm"
                  :disabled="busy"
                  data-testid="restore-question"
                  @click="restore(detail)"
                >
                  Restore
                </Button>
                <Button
                  v-else
                  variant="outline"
                  size="sm"
                  data-testid="remove-question"
                  @click="openRemove(detail)"
                >
                  Remove this question
                </Button>
              </div>
            </template>
          </div>
        </div>

        <div
          v-if="listLoading && !pageData"
          class="space-y-3 px-4 py-4"
          aria-busy="true"
          data-testid="questions-loading"
        >
          <span class="sr-only">Loading questions</span>
          <Skeleton v-for="n in 3" :key="n" class="h-10" />
        </div>
        <div
          v-else-if="pageData && !shown.length"
          class="space-y-2 px-4 py-8 text-center"
          data-testid="questions-empty"
        >
          <p class="text-sm text-muted-foreground">No questions match these filters.</p>
          <Button v-if="filtering" variant="outline" size="sm" @click="clearFilters">
            Clear filters
          </Button>
        </div>
      </div>

      <div v-if="pages > 1" class="flex justify-end gap-2">
        <Button variant="outline" size="sm" :disabled="page === 0" @click="page -= 1">
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
      </div>
    </template>

    <Dialog :open="excerptFor !== null" @update:open="(v) => !v && (excerptFor = null)">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>What the model was given</DialogTitle>
          <DialogDescription>{{ excerptFor?.question.question }}</DialogDescription>
        </DialogHeader>
        <div class="max-h-[60vh] space-y-4 overflow-y-auto" data-testid="excerpts">
          <p v-if="excerptLoading" class="text-sm text-muted-foreground">Loading…</p>
          <p v-else-if="excerptError" class="text-sm text-destructive">{{ excerptError }}</p>
          <p v-else-if="!excerpts.length" class="text-sm text-muted-foreground">
            Nothing was sent with this question.
          </p>
          <div v-for="(fragment, i) in excerpts" v-else :key="i" class="space-y-1">
            <div class="flex items-center gap-2">
              <p class="text-xs text-muted-foreground">
                From “{{ fragment.document_title || fragment.file_name }}”
              </p>
              <Badge
                v-if="fragment.is_source"
                variant="outline"
                class="border-transparent bg-primary/10 text-primary"
              >
                Right passage
              </Badge>
            </div>
            <p class="text-sm whitespace-pre-line">{{ fragment.content }}</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog :open="overrideFor !== null" @update:open="(v) => !v && closeOverride()">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change a verdict</DialogTitle>
          <DialogDescription>{{ overrideFor?.question.question }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-4">
          <fieldset class="space-y-2">
            <legend class="text-sm font-medium">Answer</legend>
            <RadioGroup v-model="overrideArm" class="gap-2">
              <div v-for="arm in overrideArms" :key="arm" class="flex items-center gap-2">
                <RadioGroupItem :id="`override-arm-${arm}`" :value="arm" />
                <Label :for="`override-arm-${arm}`" class="font-normal">{{ ARM_LABEL[arm] }}</Label>
              </div>
            </RadioGroup>
          </fieldset>
          <fieldset class="space-y-2">
            <legend class="text-sm font-medium">Verdict</legend>
            <RadioGroup v-model="overrideVerdictValue" class="gap-2">
              <div v-for="v in VERDICTS" :key="v" class="flex items-center gap-2">
                <RadioGroupItem :id="`override-verdict-${v}`" :value="v" />
                <Label :for="`override-verdict-${v}`" class="font-normal">
                  {{ verdictLabel(v) }}
                </Label>
              </div>
            </RadioGroup>
          </fieldset>
          <div class="space-y-2">
            <Label for="override-reason">Reason (optional)</Label>
            <Textarea id="override-reason" v-model="overrideReason" data-testid="override-reason" />
          </div>
        </div>
        <DialogFooter class="sm:justify-between">
          <Button
            v-if="currentOverrideId"
            variant="ghost"
            :disabled="busy"
            data-testid="withdraw-override"
            @click="withdraw"
          >
            Withdraw override
          </Button>
          <span v-else />
          <div class="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" :disabled="busy" @click="closeOverride">Cancel</Button>
            <Button
              :disabled="busy || !overrideArm"
              data-testid="save-override"
              @click="saveOverride"
            >
              Save verdict
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog :open="removeFor !== null" @update:open="(v) => !v && closeRemove()">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remove this question?</DialogTitle>
          <DialogDescription>
            It is taken out of every figure in this run, for every model.
          </DialogDescription>
        </DialogHeader>
        <p class="text-sm">{{ removeFor?.question.question }}</p>
        <div class="space-y-2">
          <Label for="remove-note">Reason (optional)</Label>
          <Textarea id="remove-note" v-model="removeNote" />
        </div>
        <div class="flex items-center gap-2">
          <Checkbox id="remove-retire" v-model="removeRetire" data-testid="remove-retire" />
          <Label for="remove-retire" class="font-normal">Also skip it in future runs</Label>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="busy" @click="closeRemove">Cancel</Button>
          <Button
            variant="destructive"
            :disabled="busy"
            data-testid="confirm-remove"
            @click="confirmRemove"
          >
            Remove question
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { ChevronDown, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type {
  BenchmarkArmDetail,
  BenchmarkQuestionDetail,
  BenchmarkQuestionPage,
  BenchmarkQuestionRow,
  BenchmarkReportFragment,
  BenchmarkVerdict,
} from '@/api/types'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { apiErrorDetail } from '@/lib/errors'
import InfoTip from '../InfoTip.vue'
import { useReport, useRun } from './context'
import { ARM_LABEL, GROUP_LABEL, kindLabel, modelName, verdictLabel } from './labels'
import { heldOf, isOutcome } from './selectors'
import { ARM_KEY, type Arm, type Group } from './types'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const PAGE_SIZE = 25
type GroupFilter = Group | 'all' | 'excluded'
const ARMS: Arm[] = ['closed', 'ctx']
const ARM_SHORT: Record<Arm, string> = { closed: 'On its own', ctx: 'With your data' }
const VERDICTS: BenchmarkVerdict[] = ['correct', 'abstain', 'hallucinate']
const GROUPS: Group[] = ['fixed', 'either', 'still', 'worse']

const report = useReport()
const run = useRun()

const name = computed(() => (run.model.value ? modelName(run.model.value) : ''))

const group = ref<GroupFilter>('all')
const page = ref(0)
const openId = ref<string | null>(null)

// --- the page of questions --------------------------------------------------------

const pageData = shallowRef<BenchmarkQuestionPage | null>(null)
/** Chip counts with excluded questions included. */
const counts = shallowRef<BenchmarkQuestionPage['counts'] | null>(null)
const excludedCount = ref(0)
const listLoading = ref(false)
const listError = ref<string | null>(null)
let listRequest = 0

/**
 * Two requests: the page itself, and a one-row request for the figure the page
 * cannot give — the excluded total, or the chip counts while excluded ones are shown.
 */
async function fetchPage(): Promise<void> {
  const model = run.model.value
  if (!model) return
  const request = ++listRequest
  const excludedView = group.value === 'excluded'
  const base = {
    model,
    generator: run.kind.value ?? undefined,
  }
  const g = group.value
  listLoading.value = true
  listError.value = null
  try {
    const [main, side] = await Promise.all([
      report.loadQuestions(run.jobId, {
        ...base,
        group: g === 'all' || g === 'excluded' ? undefined : g,
        excluded: excludedView ? 'only' : 'include',
        limit: PAGE_SIZE,
        offset: page.value * PAGE_SIZE,
      }),
      report
        .loadQuestions(run.jobId, {
          ...base,
          excluded: excludedView ? 'include' : 'only',
          limit: 1,
        })
        .catch(() => null),
    ])
    if (request !== listRequest) return
    pageData.value = main
    if (excludedView) {
      excludedCount.value = main.total
      if (side) counts.value = side.counts
      if (!main.total) group.value = 'all'
    } else {
      counts.value = main.counts
      excludedCount.value = side?.total ?? 0
    }
    if (page.value > 0 && page.value * PAGE_SIZE >= main.total) {
      page.value = Math.max(Math.ceil(main.total / PAGE_SIZE) - 1, 0)
    }
  } catch (e) {
    if (request === listRequest) listError.value = apiErrorDetail(e, 'Could not load the questions')
  } finally {
    if (request === listRequest) listLoading.value = false
  }
}

watch([group, () => run.kind.value, () => run.model.value], () => {
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

const groupChips = computed(() => {
  const c = counts.value
  const chips: { key: GroupFilter; label: string; count: number }[] = [
    { key: 'all', label: 'All questions', count: c?.all ?? 0 },
    ...GROUPS.map((g) => ({ key: g, label: GROUP_LABEL[g], count: c?.[g] ?? 0 })),
  ]
  if (excludedCount.value > 0)
    chips.push({ key: 'excluded', label: 'Excluded', count: excludedCount.value })
  return chips
})

const shown = computed(() => pageData.value?.items ?? [])
const filtering = computed(() => group.value !== 'all' || !!run.kind.value)
const pages = computed(() => Math.max(1, Math.ceil((pageData.value?.total ?? 0) / PAGE_SIZE)))
const range = computed(() => {
  const n = pageData.value?.total ?? 0
  if (!n) return '0'
  const from = page.value * PAGE_SIZE + 1
  return `${from}–${Math.min(n, from + PAGE_SIZE - 1)}`
})

function clearFilters(): void {
  group.value = 'all'
  run.setKind(null)
}

// --- one question -------------------------------------------------------------------

const detail = shallowRef<BenchmarkQuestionDetail | null>(null)
const detailError = ref<string | null>(null)
let detailRequest = 0

async function loadDetail(qaId: string): Promise<void> {
  const model = run.model.value
  if (!model) return
  const request = ++detailRequest
  detailError.value = null
  try {
    const d = await report.loadQuestion(run.jobId, qaId, model)
    if (request === detailRequest) detail.value = d
  } catch (e) {
    if (request === detailRequest)
      detailError.value = apiErrorDetail(e, 'Could not load this question')
  }
}

function toggle(qaId: string): void {
  if (openId.value === qaId) {
    openId.value = null
    return
  }
  openId.value = qaId
  detail.value = null
  void loadDetail(qaId)
}

function articleOf(q: BenchmarkQuestionRow): string {
  return q.document_title || q.file_name || 'Unknown article'
}

function rowVerdict(q: BenchmarkQuestionRow, arm: Arm): BenchmarkVerdict | null {
  return arm === 'closed' ? q.verdict_alone : q.verdict_with
}

function armOf(d: BenchmarkQuestionDetail, arm: Arm): BenchmarkArmDetail | null {
  return d.arms[ARM_KEY[arm]]
}

function verdictClass(verdict: string | null | undefined): string {
  if (verdict === 'correct') return 'border-transparent bg-primary/10 text-primary'
  if (verdict === 'abstain') return 'border-transparent bg-muted text-muted-foreground'
  if (verdict === 'hallucinate') return 'border-transparent bg-warning/20 text-foreground'
  return 'text-muted-foreground'
}

function judgeVerdict(verdict: BenchmarkVerdict | null): string {
  return verdict ? verdictLabel(verdict) : '—'
}

function ofText(part: number | undefined, whole: number | undefined): string {
  return part === undefined || whole === undefined ? '—' : `${part} of ${whole}`
}

function heldText(d: BenchmarkQuestionDetail, arm: Arm): string {
  const held = heldOf(armOf(d, arm)?.denial)
  return ofText(held?.held, held?.of)
}

function repeatText(d: BenchmarkQuestionDetail, arm: Arm): string {
  const repeats = armOf(d, arm)?.repeats
  return repeats?.trials ? ofText(repeats.right, repeats.trials) : '—'
}

function hasHeld(d: BenchmarkQuestionDetail): boolean {
  return ARMS.some((arm) => !!armOf(d, arm)?.denial)
}

function hasRepeats(d: BenchmarkQuestionDetail): boolean {
  return ARMS.some((arm) => !!armOf(d, arm)?.repeats?.trials)
}

function ordinal(n: number): string {
  const tens = n % 100
  if (tens >= 11 && tens <= 13) return `${n}th`
  return `${n}${['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`
}

function retrievalText(d: BenchmarkQuestionDetail): string | null {
  const r = d.arms.with?.retrieval
  if (!r) return null
  const { hit, rank, context_docs: contextDocs } = r
  if (hit === null && contextDocs === null) return null
  const given =
    contextDocs === null
      ? 'Given passages from your archive'
      : `Given ${contextDocs} ${contextDocs === 1 ? 'passage' : 'passages'} from your archive`
  if (hit === null) return given
  if (hit && rank !== null && (contextDocs === null || rank <= contextDocs)) {
    return `${given}; the right one ranked ${ordinal(rank)}`
  }
  return `${given}; none was the right one`
}

// --- source passages ------------------------------------------------------------

const excerptFor = shallowRef<BenchmarkQuestionDetail | null>(null)
const excerpts = ref<BenchmarkReportFragment[]>([])
const excerptLoading = ref(false)
const excerptError = ref<string | null>(null)
let excerptRequest = 0

async function openExcerpt(d: BenchmarkQuestionDetail): Promise<void> {
  const model = run.model.value
  if (!model) return
  const request = ++excerptRequest
  excerptFor.value = d
  excerpts.value = []
  excerptError.value = null
  excerptLoading.value = true
  try {
    const fragments = await report.loadFragments(run.jobId, d.question.qa_id, model)
    if (request === excerptRequest) excerpts.value = fragments
  } catch (e) {
    if (request === excerptRequest)
      excerptError.value = apiErrorDetail(e, 'Could not load the passages')
  } finally {
    if (request === excerptRequest) excerptLoading.value = false
  }
}

// --- owner actions ------------------------------------------------------------------

const busy = ref(false)
const overrideFor = shallowRef<BenchmarkQuestionDetail | null>(null)
const overrideArm = ref<Arm | undefined>(undefined)
const overrideVerdictValue = ref<BenchmarkVerdict>('correct')
const overrideReason = ref('')

const overrideArms = computed(() =>
  ARMS.filter((arm) => overrideFor.value && armOf(overrideFor.value, arm)),
)
const currentOverrideId = computed(() => {
  const arm = overrideArm.value
  const d = overrideFor.value
  return arm && d ? (armOf(d, arm)?.override?.id ?? null) : null
})

function verdictOf(d: BenchmarkQuestionDetail | null, arm: Arm | undefined): BenchmarkVerdict {
  const verdict = d && arm ? armOf(d, arm)?.verdict : undefined
  return verdict && isOutcome(verdict) ? verdict : 'correct'
}

watch(overrideArm, (arm) => {
  overrideVerdictValue.value = verdictOf(overrideFor.value, arm)
})

function openOverride(d: BenchmarkQuestionDetail): void {
  overrideFor.value = d
  overrideReason.value = ''
  overrideArm.value = d.arms.with ? 'ctx' : 'closed'
  overrideVerdictValue.value = verdictOf(d, overrideArm.value)
}

function closeOverride(): void {
  if (!busy.value) overrideFor.value = null
}

async function saveOverride(): Promise<void> {
  const arm = overrideArm.value
  const answer = arm && overrideFor.value ? armOf(overrideFor.value, arm) : null
  if (!answer) return
  busy.value = true
  try {
    await report.overrideVerdict(
      run.jobId,
      answer.result_id,
      overrideVerdictValue.value,
      overrideReason.value,
    )
    toast.success('Verdict changed')
    overrideFor.value = null
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not change this verdict'))
  } finally {
    busy.value = false
  }
}

async function withdraw(): Promise<void> {
  const id = currentOverrideId.value
  if (!id) return
  busy.value = true
  try {
    await report.withdrawOverride(run.jobId, id)
    toast.success('Override withdrawn')
    overrideFor.value = null
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not withdraw this override'))
  } finally {
    busy.value = false
  }
}

const removeFor = shallowRef<BenchmarkQuestionDetail | null>(null)
const removeNote = ref('')
const removeRetire = ref(false)

function openRemove(d: BenchmarkQuestionDetail): void {
  removeFor.value = d
  removeNote.value = ''
  removeRetire.value = false
}

function closeRemove(): void {
  if (!busy.value) removeFor.value = null
}

async function confirmRemove(): Promise<void> {
  const d = removeFor.value
  if (!d) return
  busy.value = true
  try {
    await report.excludeQuestion(
      run.jobId,
      d.question.qa_id,
      removeNote.value.trim(),
      removeRetire.value,
    )
    toast.success('Question removed')
    removeFor.value = null
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not remove this question'))
  } finally {
    busy.value = false
  }
}

async function restore(d: BenchmarkQuestionDetail): Promise<void> {
  busy.value = true
  try {
    await report.restoreQuestion(run.jobId, d.question.qa_id)
    toast.success('Question restored')
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not restore this question'))
  } finally {
    busy.value = false
  }
}
</script>
