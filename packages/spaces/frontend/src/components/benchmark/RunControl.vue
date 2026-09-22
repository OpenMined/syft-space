<template>
  <div v-if="loading" class="space-y-3">
    <Skeleton class="h-28 w-full" />
  </div>

  <!-- No benchmark is wired to this Space at all. Saying so here, with the way
       out, beats an empty form that cannot be submitted. -->
  <section
    v-else-if="!target?.connection_id && !target?.measured"
    class="border border-border/50 rounded-lg p-6 text-center"
  >
    <Gauge class="h-7 w-7 text-muted-foreground/50 mx-auto mb-3" />
    <h3 class="text-sm font-medium text-foreground mb-1">
      {{ hasBenchmark ? 'This endpoint is not measured' : 'No benchmark is connected' }}
    </h3>
    <p class="text-xs text-muted-foreground max-w-md mx-auto mb-4">
      <template v-if="hasBenchmark">
        Nothing is grading this endpoint yet. Turn it on and the benchmark will build questions from
        its index and ask them back.
      </template>
      <template v-else>
        Measuring is a separate service, and this Space is not wired to one yet.
      </template>
    </p>
    <Button v-if="hasBenchmark" size="sm" :disabled="saving" @click="startMeasuring">
      <Play class="h-4 w-4 mr-1.5" />
      Measure this endpoint
    </Button>
    <Button v-else size="sm" variant="outline" @click="router.push({ name: 'benchmark' })">
      Connect a benchmark
    </Button>
  </section>

  <section v-else class="border border-border/50 rounded-lg p-5 space-y-5">
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div class="space-y-1">
        <h2 class="heading-3 text-foreground flex items-center gap-2">
          <Gauge class="h-5 w-5 text-muted-foreground" />
          Measuring
        </h2>
        <p class="text-xs text-muted-foreground">
          {{ target?.connection_name || 'Benchmark' }}
          <span v-if="target?.collection || target?.resolved_collection">
            · index collection {{ target.collection || target.resolved_collection }}
          </span>
          <span v-if="target?.synced_at"> · settings handed over {{ ago(target.synced_at) }}</span>
          <span v-else class="text-amber-600 dark:text-amber-400">
            · settings not yet handed over
          </span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="checking" @click="check">
          {{ checking ? 'Checking…' : 'Check access' }}
        </Button>
        <Button
          v-if="running"
          variant="outline"
          size="sm"
          class="text-destructive hover:text-destructive"
          :disabled="cancelling"
          @click="cancel"
        >
          <Square class="h-4 w-4 mr-1.5" />
          {{ cancelling ? 'Stopping…' : 'Stop' }}
        </Button>
        <template v-else>
          <Button
            variant="outline"
            size="sm"
            :disabled="generating || starting || !target?.enabled"
            @click="runGenerate"
          >
            <RefreshCw class="h-4 w-4 mr-1.5" />
            {{ generating ? 'Building…' : 'Generate questions' }}
          </Button>
          <Button
            size="sm"
            :disabled="generating || starting || !target?.enabled"
            @click="runEvaluate"
          >
            <Play class="h-4 w-4 mr-1.5" />
            {{ starting ? 'Starting…' : limit ? 'Trial run' : 'Run test' }}
          </Button>
        </template>
      </div>
    </div>

    <!-- Two actions rather than one because asking is the expensive half: it
         calls a paid model once per question, per arm, per model under test.
         A launch that only wanted a fresh set must not be charged for it. -->
    <p v-if="!running" class="text-xs text-muted-foreground -mt-2">
      <strong class="text-foreground">Generate questions</strong> builds the question set from the
      index and nothing else — no model under test is asked anything, and there is no card.
      <strong class="text-foreground">Run test</strong> asks the questions already in the set and
      grades the answers; it never rebuilds the set itself, so run
      <strong class="text-foreground">Generate questions</strong> first if the corpus has changed.
    </p>

    <!-- How much to ask for. Empty means the whole set; a number turns the run
         into a trial. It caps both actions — chunks read per generator while
         building, questions asked per generator while testing. Publishing is
         a separate decision on top of testing: a thin sample is not hidden but
         named on the card itself. -->
    <div v-if="!running" class="flex flex-wrap items-end gap-4">
      <div class="space-y-1.5">
        <Label for="bm-limit" class="text-sm">Questions per generator</Label>
        <Input
          id="bm-limit"
          v-model="limit"
          type="number"
          min="1"
          placeholder="all of them"
          class="h-9 w-44"
        />
      </div>
      <label class="flex items-center gap-2 text-xs text-foreground pb-2.5 cursor-pointer">
        <Checkbox v-model="publish" />
        Publish the card when the test finishes
      </label>
      <p class="text-xs text-muted-foreground pb-2.5 max-w-md">
        <template v-if="limit">
          A trial: {{ limit }} per generator, for either button. Each generator is a separate skill,
          so the cap is per generator rather than overall — a total cap would quietly drop whole
          skills from the figures. A card published from so few questions carries that on its face.
        </template>
        <template v-else>
          The whole set, every arm and check that is configured. Running the test this way takes
          hours and costs money at the provider.
        </template>
      </p>
    </div>

    <!-- A run in flight. Two counts, because they are two different things:
         passes are what the run is made of, questions are what a pass is made
         of, and one bar for both would misreport both. -->
    <div v-if="job" class="rounded-md bg-muted/40 px-4 py-3 space-y-2.5">
      <div class="flex items-center justify-between gap-3 text-xs">
        <span class="font-medium text-foreground">{{ stateWords(job) }}</span>
        <span class="text-muted-foreground">
          <template v-if="running && elapsed">{{ elapsed }} so far</template>
          <template v-else-if="!running">{{ ago(job.finished_at ?? job.created_at) }}</template>
        </span>
      </div>

      <!-- Passes: what the run is made of. -->
      <div v-if="job.total" class="space-y-1">
        <div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>
            Pass {{ Math.min(job.done + (running ? 1 : 0), job.total) }} of {{ job.total }}
          </span>
          <span v-if="job.arm">{{ armWords(job.arm) }}</span>
        </div>
        <div class="h-1.5 rounded-full bg-border overflow-hidden">
          <div
            class="h-full rounded-full transition-all"
            :class="running ? 'bg-primary' : 'bg-muted-foreground/40'"
            :style="{ width: passShare }"
          />
        </div>
      </div>

      <!-- Questions inside the pass that is running. -->
      <div v-if="running && job.step_total" class="space-y-1">
        <div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>
            {{ job.step_done }} of {{ job.step_total }} questions
            <span v-if="job.block"> · {{ blockWords(job.block) }}</span>
            <span v-if="job.model"> · {{ job.model }}</span>
          </span>
          <span v-if="stepLeft">≈ {{ stepLeft }} left in this pass</span>
        </div>
        <div class="h-1 rounded-full bg-border overflow-hidden">
          <div
            class="h-full rounded-full bg-primary/50 transition-all"
            :style="{ width: stepShare }"
          />
        </div>
      </div>

      <p v-if="running && questionsTotal" class="text-xs text-muted-foreground">
        {{ questionsDone }} of {{ questionsTotal }} questions overall. There is no estimate for the
        whole run on purpose: a pass that pushes back, or repeats at several temperatures, costs
        several times one that asks once, and a single average would be wrong in both directions.
      </p>
      <p
        v-else-if="running && !job.total && job.phase !== 'generate'"
        class="text-xs text-muted-foreground"
      >
        Working out what to run.
      </p>
      <p v-if="job.message" class="text-xs text-muted-foreground">{{ job.message }}</p>
      <p
        v-for="problem in problems"
        :key="problem"
        class="text-xs text-amber-700 dark:text-amber-400"
      >
        {{ runProblemWords(problem) }}
      </p>
    </div>

    <!-- What the benchmark found when it tried both roads. -->
    <div v-if="access" class="rounded-md px-4 py-3 text-xs space-y-1.5" :class="accessTone">
      <div class="flex items-center gap-2 font-medium">
        <component :is="access.ok ? CheckCircle2 : TriangleAlert" class="h-4 w-4" />
        <span v-if="access.ok">Both roads work</span>
        <span v-else>Something is in the way</span>
      </div>
      <p v-if="access.corpus">
        Index: {{ access.chunks }} fragments in {{ access.documents }} documents,
        {{ access.usable }} usable — over {{ access.transport }}.
      </p>
      <p v-if="access.endpoint">
        Endpoint answers in <code>{{ access.response_type }}</code> mode.
      </p>
      <p v-for="(code, arm) in access.blocked_arms" :key="arm">
        Arm {{ arm }}: {{ blockedArmWords(code) }}
      </p>
      <p v-for="problem in access.problems" :key="problem">{{ problem }}</p>
      <div v-if="access.available.length" class="pt-1">
        <span>Collections in the index: </span>
        <button
          v-for="name in access.available"
          :key="name"
          type="button"
          class="underline underline-offset-2 mr-2"
          @click="useCollection(name)"
        >
          {{ name }}
        </button>
      </div>
    </div>

    <!-- Every past launch of this endpoint, generate-only ones included. This
         is where "what actually happened" lives once a run is no longer the
         one in progress — the box above only ever shows the latest. -->
    <details v-if="history.length" class="group">
      <summary
        class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
      >
        <ChevronRight class="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
        Measurement history ({{ history.length }})
      </summary>

      <div class="pt-3 space-y-3">
        <p class="text-xs text-muted-foreground max-w-2xl">
          Every launch against this endpoint, whether it built the question set, tested it, or both.
          Deleting one removes its own passes and verdicts — the question set itself belongs to the
          endpoint, not to any one launch, and is not touched.
        </p>
        <ul class="divide-y divide-border/50">
          <li
            v-for="row in history"
            :key="row.id"
            class="py-2.5 flex items-start justify-between gap-3 text-xs"
          >
            <div class="space-y-0.5 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-foreground">{{ stateWords(row) }}</span>
                <span class="text-muted-foreground">· {{ historyKindWords(row) }}</span>
                <span v-if="row.trigger === 'schedule'" class="text-muted-foreground">
                  · scheduled
                </span>
              </div>
              <p class="text-muted-foreground">
                {{ ago(row.finished_at ?? row.created_at) }}
              </p>
              <p v-if="row.card" class="text-muted-foreground">
                {{ cardSummaryWords(row.card) }}
              </p>
              <p v-else-if="row.message" class="text-muted-foreground">{{ row.message }}</p>
              <p v-if="row.error" class="text-amber-700 dark:text-amber-400">{{ row.error }}</p>
            </div>
            <Button
              v-if="settled(row)"
              variant="ghost"
              size="sm"
              class="text-destructive hover:text-destructive shrink-0 h-7 w-7 p-0"
              :disabled="deletingId === row.id"
              :aria-label="`Delete this run (${ago(row.finished_at ?? row.created_at)})`"
              @click="removeJob(row)"
            >
              <Trash2 class="h-3.5 w-3.5" />
            </Button>
          </li>
        </ul>
      </div>
    </details>

    <!-- What differs about this endpoint. Everything unset is inherited, and
         the inherited value is shown rather than implied. -->
    <details class="group">
      <summary
        class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
      >
        <ChevronRight class="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
        Settings for this endpoint
      </summary>

      <div class="pt-4 space-y-5">
        <div class="flex items-start gap-3">
          <Checkbox id="bm-enabled" v-model="enabled" class="mt-0.5" />
          <div>
            <Label for="bm-enabled" class="text-sm text-foreground cursor-pointer">
              Keep measuring this endpoint
            </Label>
            <p class="text-xs text-muted-foreground mt-0.5">
              Unticking pauses it. Settings and past runs are kept — this is not the same as taking
              the endpoint out of the benchmark.
            </p>
          </div>
        </div>

        <div class="grid sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <Label for="bm-collection" class="text-sm">Index collection</Label>
            <Input
              id="bm-collection"
              v-model="collection"
              :placeholder="target?.resolved_collection || 'resolved from the dataset'"
              class="h-9"
            />
            <p class="text-xs text-muted-foreground">
              Left blank, it is worked out from the endpoint's dataset. Fill it in only when that
              turns out to be wrong.
            </p>
          </div>
          <div class="space-y-1.5">
            <Label for="bm-schedule" class="text-sm">When it runs</Label>
            <div class="flex gap-2">
              <select
                id="bm-schedule"
                v-model="schedule"
                class="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">By hand, from here</option>
                <option value="24h">Every day</option>
                <option value="12h">Every 12 hours</option>
                <option value="6h">Every 6 hours</option>
                <option value="1h">Every hour</option>
              </select>
              <Input
                v-if="schedule === '24h'"
                v-model="scheduleAt"
                placeholder="03:00"
                class="h-9 w-24"
                aria-label="Hour of the launch, UTC"
              />
            </div>
            <p class="text-xs text-muted-foreground">
              <template v-if="schedule === '24h'">
                The hour is <strong>UTC</strong> — the benchmark keeps it that way because a service
                in a container cannot know what your night is.
              </template>
              <template v-else-if="schedule">
                The step runs from the previous launch, not from an hour of the day.
              </template>
              <template v-else>
                Nothing runs until you press Measure. A corpus that changes daily usually wants a
                nightly run; one kept for reference, far less.
              </template>
            </p>
            <p v-if="nextRun" class="text-xs text-muted-foreground">Next run {{ nextRun }}.</p>
            <p v-else-if="schedule" class="text-xs text-muted-foreground">
              The benchmark works out the moment when it saves; it will show here once it has.
            </p>
          </div>
        </div>

        <div v-if="probeFields.length" class="space-y-4">
          <div class="border-b border-border/50 pb-1">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              What differs here
            </p>
            <p class="text-xs text-muted-foreground mt-1 max-w-2xl mb-2">
              Anything left at its default follows the Space-wide setting. Judges, arms and
              thresholds are not here on purpose: they are what the card declares, and two endpoints
              graded differently would be quietly incomparable.
            </p>
          </div>
          <!-- The probe names no models, so nothing here reaches the
               catalogue. Passed anyway: which fields carry one is the
               benchmark's to decide. -->
          <LayerForm
            v-model="probe"
            :fields="probeFields"
            :inherited="inheritedProbe"
            :connection-id="target?.connection_id ?? ''"
          />
        </div>

        <div class="flex items-center gap-3">
          <Button size="sm" :disabled="saving" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            class="text-destructive hover:text-destructive"
            @click="stopMeasuring"
          >
            Stop measuring this endpoint
          </Button>
        </div>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
/**
 * Measuring one endpoint: whether, how, and go.
 *
 * This sits above the card on the endpoint's Benchmark tab, and the order is
 * the order of the owner's questions — is anyone measuring this, can they
 * reach it, what is happening right now, and only then what exactly differs
 * about it. The settings are folded away because most endpoints differ in
 * nothing, and a form nobody needs should not be the first thing on the page.
 *
 * While a run is going the job is polled. A measurement takes hours, so the
 * poll is slow on purpose: it is watching for a phase to change, not for a
 * number to tick.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import {
  CheckCircle2,
  ChevronRight,
  Gauge,
  Play,
  RefreshCw,
  Square,
  Trash2,
  TriangleAlert,
} from 'lucide-vue-next'

import LayerForm from '@/components/benchmark/LayerForm.vue'
import {
  armWords,
  blockWords,
  blockedArmWords,
  runProblemWords,
} from '@/components/benchmark/labels'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { apiErrorDetail } from '@/lib/errors'
import { formatTimeAgo } from '@/lib/formatters'
import type {
  BenchmarkCard,
  BenchmarkCheck,
  BenchmarkJob,
  BenchmarkLayer,
  BenchmarkTarget,
} from '@/api/types'

// Five seconds. A run takes hours and its phases last minutes; polling faster
// would be asking the benchmark a question whose answer cannot have changed.
const POLL_MS = 5000

const props = defineProps<{ slug: string }>()
const emit = defineEmits<{ finished: [] }>()

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const starting = ref(false)
const generating = ref(false)
const checking = ref(false)
const cancelling = ref(false)
const deletingId = ref('')

const target = ref<BenchmarkTarget | null>(null)
const job = ref<BenchmarkJob | null>(null)
// Every launch of this endpoint, newest first — `job` is only ever the first
// of these, kept apart because the running box reads it every poll and the
// history list does not need to re-render just because a step count ticked.
const history = ref<BenchmarkJob[]>([])
const access = ref<BenchmarkCheck | null>(null)

const enabled = ref(true)
const collection = ref('')
const schedule = ref('')
const scheduleAt = ref('')
const probe = ref<BenchmarkLayer>({})

// How many questions to ask. Empty means the whole set; a number makes the run a trial.
const limit = ref<string>('')
const publish = ref(true)

// Pace baseline: when, and at which question, we first saw THIS pass.
// Kept locally rather than taken from the job, because the question is not how
// long the job has been going but how fast it is going right now: a pass under
// pressure or with retries counts several times slower than usual, and an
// average over the whole job would mislead in both directions.
const paceKey = ref('')
const paceFrom = ref(0)
const paceAt = ref(0)
const now = ref(Date.now())

let timer: ReturnType<typeof setInterval> | null = null
let clock: ReturnType<typeof setInterval> | null = null

const hasBenchmark = computed(() => Boolean(target.value?.connection_id))

// Mirrors JobState.final in the benchmark itself (packages/benchmark,
// src/syft_benchmark/config.py): these three are the states a job never moves
// out of again.
//
// Named as the terminal set rather than as the in-flight one on purpose. The
// two mistakes are not symmetric: reading a live run as finished stops the
// poll, freezes the progress the owner is watching and reports a failure that
// did not happen, while reading a finished run as live only re-reads a row
// that no longer changes.
const TERMINAL_STATES = new Set<BenchmarkJob['state']>(['succeeded', 'failed', 'cancelled'])

/** Whether this run is over. A stamped end counts even if the state is new to us. */
function settled(current: BenchmarkJob | null): boolean {
  return Boolean(current && (TERMINAL_STATES.has(current.state) || current.finished_at))
}

const running = computed(() => Boolean(job.value) && !settled(job.value))
const probeFields = computed(() => target.value?.fields?.probe ?? [])

/**
 * When the benchmark says it will next measure, in the reader's own time zone.
 *
 * Stored and fired in UTC — the service cannot know whose night it is — but
 * shown here in local time, because "next run 03:00" is only useful to someone
 * who knows which 03:00 is meant. The form says UTC where the hour is set; this
 * says it in the reader's terms where it is read.
 */
const nextRun = computed(() => {
  const raw = target.value?.next_run_at
  if (!raw) return ''
  const moment = new Date(raw)
  return Number.isNaN(moment.valueOf()) ? '' : moment.toLocaleString()
})

// The benchmark joins what went wrong with semicolons; split back so each
// reason is its own line rather than one long run-on.
const problems = computed(() =>
  (job.value?.error ?? '')
    .split(';')
    .map((part) => part.trim())
    .filter(Boolean),
)

/** What this endpoint falls back to: the Space-wide layer, then the installation. */
const inheritedProbe = computed(() => ({
  ...target.value?.defaults?.probe,
  ...target.value?.connection_probe,
}))

const questionsTotal = computed(() => (job.value ? job.value.step_total * job.value.total : 0))
const questionsDone = computed(() =>
  job.value ? job.value.step_total * job.value.done + job.value.step_done : 0,
)

const passShare = computed(() => {
  const current = job.value
  if (!current?.total) return '0%'
  return `${Math.min(100, (current.done / current.total) * 100)}%`
})

const stepShare = computed(() => {
  const current = job.value
  if (!current?.step_total) return '0%'
  return `${Math.min(100, (current.step_done / current.step_total) * 100)}%`
})

/** How long the job has been running. */
const elapsed = computed(() => {
  const started = job.value?.started_at
  if (!started) return ''
  return duration(now.value - new Date(started).getTime())
})

/**
 * How much is left in the current pass — from the pace measured on that pass itself.
 *
 * While too few questions have gone by there is no estimate at all: a number
 * built on two points looks just as confident as one built on a hundred, and lies.
 */
const stepLeft = computed(() => {
  const current = job.value
  if (!current?.step_total || !paceAt.value) return ''
  const asked = current.step_done - paceFrom.value
  const spent = now.value - paceAt.value
  if (asked < 3 || spent < 5000) return ''
  const left = current.step_total - current.step_done
  if (left <= 0) return ''
  return duration((spent / asked) * left)
})

function duration(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000))
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  return `${hours} h ${minutes % 60} min`
}

const accessTone = computed(() =>
  access.value?.ok
    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
    : 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
)

async function load() {
  try {
    const fresh = await benchmarksApi.getTarget(props.slug)
    target.value = fresh
    job.value = fresh.last_job
    enabled.value = fresh.enabled
    collection.value = fresh.collection
    schedule.value = fresh.schedule
    scheduleAt.value = fresh.schedule_at
    probe.value = { ...fresh.probe }
  } catch {
    toast.error('Could not read the benchmark settings for this endpoint')
  } finally {
    loading.value = false
  }
}

async function refreshJob() {
  try {
    const jobs = await benchmarksApi.listJobs(props.slug)
    history.value = jobs
    const latest = jobs[0] ?? null
    const wasRunning = running.value
    trackPace(latest)
    job.value = latest
    // The card only exists once a run has finished, so the panel below is told
    // to re-read itself rather than keep showing yesterday's figures.
    if (wasRunning && settled(latest)) {
      emit('finished')
    }
  } catch {
    // Left alone on purpose: a benchmark that blinked should not wipe the
    // progress the owner is watching.
  }
}

function startPolling() {
  if (timer) return
  timer = setInterval(refreshJob, POLL_MS)
  // The clock ticks separately from polling: "running for 4 minutes" should grow
  // every second, not jump in fives along with the service's replies.
  clock = setInterval(() => (now.value = Date.now()), 1000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (clock) {
    clearInterval(clock)
    clock = null
  }
}

watch(running, (isRunning) => (isRunning ? startPolling() : stopPolling()), { immediate: true })

async function startMeasuring() {
  saving.value = true
  try {
    target.value = await benchmarksApi.saveTarget(props.slug, { enabled: true, probe: {} })
    await load()
    toast.success('This endpoint is now measured')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not start measuring this endpoint'))
  } finally {
    saving.value = false
  }
}

/** Push the settings on screen and re-read them. No toast: callers decide that. */
async function persist(): Promise<void> {
  await benchmarksApi.saveTarget(props.slug, {
    enabled: enabled.value,
    collection: collection.value,
    probe: probe.value,
    schedule: schedule.value,
    // The hour only means anything to a daily interval; sending it with a
    // six-hourly one would leave a value in the form that decides nothing.
    schedule_at: schedule.value === '24h' ? scheduleAt.value : '',
  })
  await load()
}

async function save() {
  saving.value = true
  try {
    await persist()
    toast.success('Saved')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not save'))
  } finally {
    saving.value = false
  }
}

async function stopMeasuring() {
  try {
    await benchmarksApi.stopMeasuring(props.slug)
    access.value = null
    await load()
    toast.success('Taken out of the benchmark. Published figures were not touched.')
  } catch {
    toast.error('Could not take this endpoint out')
  }
}

async function check() {
  checking.value = true
  try {
    access.value = await benchmarksApi.checkTarget(props.slug)
  } catch (error) {
    toast.error(apiErrorDetail(error, 'The benchmark did not answer'))
  } finally {
    checking.value = false
  }
}

/**
 * Ask and grade — never rebuilds the question set. `Generate questions` is
 * the button for that, kept separate on purpose: asking is the expensive
 * half, and a launch meant only to refresh the set must not be charged for it.
 */
async function runEvaluate() {
  starting.value = true
  const capped = Number(limit.value) || null
  try {
    // Against what is on screen, not whatever was last saved - a probe edit
    // followed by "Run test" must not silently measure the old settings.
    await persist()
    const started = await benchmarksApi.startRun(props.slug, {
      generate: false,
      limit: capped,
      publish: publish.value,
    })
    onLaunched(started)
    toast.success(capped ? 'Trial run queued' : 'Run queued')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'The benchmark did not take the run'))
  } finally {
    starting.value = false
  }
}

/** Build the question set from the index. Nothing is asked, nothing graded. */
async function runGenerate() {
  generating.value = true
  const capped = Number(limit.value) || null
  try {
    // Same reasoning as runEvaluate: the set is built from the probe on
    // screen, not from whatever was last saved.
    await persist()
    const started = await benchmarksApi.startRun(props.slug, {
      generate: true,
      evaluate: false,
      limit: capped,
      publish: false,
    })
    onLaunched(started)
    toast.success('Building the question set')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'The benchmark did not take the run'))
  } finally {
    generating.value = false
  }
}

/** Common to both buttons: show it at once, poll it, and put it at the top of the history. */
function onLaunched(started: BenchmarkJob) {
  job.value = started
  history.value = [started, ...history.value.filter((row) => row.id !== started.id)]
  resetPace()
  startPolling()
}

function resetPace() {
  paceKey.value = ''
  paceFrom.value = 0
  paceAt.value = 0
}

/** Notice when the pass changes: pace is measured per pass. */
function trackPace(current: BenchmarkJob | null) {
  if (!current || current.state !== 'running') return resetPace()
  const key = `${current.arm}/${current.block}/${current.model}`
  if (key !== paceKey.value) {
    paceKey.value = key
    paceFrom.value = current.step_done
    paceAt.value = Date.now()
  }
}

async function cancel() {
  if (!job.value) return
  cancelling.value = true
  try {
    job.value = await benchmarksApi.cancelRun(props.slug, job.value.id)
    toast.success('Asked it to stop. It finishes the question in hand and comes out.')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not stop the run'))
  } finally {
    cancelling.value = false
  }
}

function useCollection(name: string) {
  collection.value = name
  toast.info('Collection filled in — save to hand it over')
}

function stateWords(current: BenchmarkJob): string {
  switch (current.state) {
    case 'queued':
      return 'Queued — one run at a time per benchmark'
    case 'running':
      return phaseWords(current.phase)
    case 'succeeded':
      return current.error ? 'Finished, but not entirely' : 'Finished'
    case 'cancelled':
      return 'Stopped — what it measured is kept'
    case 'failed':
      return 'Did not finish'
    default:
      // A state this build has never heard of. `settled` reads it as still
      // going, so say what the phase says rather than declare a failure the
      // benchmark never reported.
      return phaseWords(current.phase)
  }
}

/** The phases of JobPhase, in the order they run. */
function phaseWords(phase: string): string {
  switch (phase) {
    case 'pending':
      return 'Getting ready'
    case 'generate':
      return 'Building questions from the corpus'
    case 'evaluate':
      return 'Asking and grading'
    case 'report':
      return 'Folding the verdicts into figures'
    case 'publish':
      return 'Handing the card over'
    case 'done':
      return 'Finishing up'
    default:
      return 'Running'
  }
}

/** What kind of launch a row in the history was, for the reader who was not watching it live. */
function historyKindWords(row: BenchmarkJob): string {
  if (row.arm) return armWords(row.arm)
  // No pass was ever planned and the job still reached the end: nothing was
  // asked because nothing was meant to be. A run that stopped short has a zero
  // here too, and calling that one a set refresh would misreport it.
  if (row.state === 'succeeded' && !row.total) return 'question set only'
  return 'measurement'
}

/** The one line a graded run leaves behind, once its card exists. */
function cardSummaryWords(card: BenchmarkCard): string {
  const label = card.kind === 'retrieval' ? 'found' : 'correct'
  const score = card.score == null ? '—' : `${Math.round(card.score * 100)}%`
  return `${score} ${label} · ${card.samples} graded`
}

async function removeJob(row: BenchmarkJob) {
  // A native confirm rather than a second click hidden in the row: deleting a
  // run cannot be undone, and the passes and verdicts it holds are gone with
  // it, not just the summary shown here.
  if (!window.confirm('Delete this run for good? Its passes and verdicts go with it.')) {
    return
  }
  deletingId.value = row.id
  try {
    await benchmarksApi.deleteJob(props.slug, row.id)
    history.value = history.value.filter((item) => item.id !== row.id)
    toast.success('Run deleted')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not delete this run'))
  } finally {
    deletingId.value = ''
  }
}

function ago(stamp: string | null): string {
  return stamp ? formatTimeAgo(stamp) : ''
}

onMounted(async () => {
  await load()
  // The history list is not part of `load()`'s target read — it comes from
  // the benchmark's own job table, and the target has no business caching a
  // list rather than the one last job it already remembers.
  await refreshJob()
})
onUnmounted(stopPolling)
</script>
