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
        Nothing is grading this endpoint yet. Turn it on to build a question set and start
        measuring.
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

  <section v-else class="border border-border/50 rounded-lg p-5 space-y-4">
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div class="space-y-1">
        <h2 class="heading-3 text-foreground flex items-center gap-2">
          <Gauge class="h-5 w-5 text-muted-foreground" />
          Measure this endpoint
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
      <Button variant="outline" size="sm" :disabled="checking" @click="check">
        {{ checking ? 'Checking…' : 'Check access' }}
      </Button>
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
      <p v-for="problem in access.problems" :key="problem">{{ problem }}</p>
    </div>

    <details
      class="group/settings"
      :open="sections.settings"
      @toggle="sections.settings = ($event.target as HTMLDetailsElement).open"
    >
      <summary
        class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
      >
        <ChevronRight class="h-3.5 w-3.5 transition-transform group-open/settings:rotate-90" />
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
                <option value="">By hand, below</option>
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
              <template v-else> Nothing runs on a schedule. Start a phase below by hand. </template>
            </p>
            <p v-if="nextRun" class="text-xs text-muted-foreground">Next run {{ nextRun }}.</p>
            <p v-else-if="schedule" class="text-xs text-muted-foreground">
              The benchmark works out the moment when it saves; it will show here once it has.
            </p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <Button size="sm" :disabled="saving" @click="persistTarget">
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

    <PhaseGroup
      title="Full run"
      :status="jobStateWords(fullJob) || 'Generate, filter, execute, judge, report'"
      :progress="progressOf(fullJob)"
      :action-label="fullAction.label"
      :action-disabled="fullAction.disabled"
      :action-destructive="fullAction.destructive"
      v-model:open="sections.full"
      @action="fullAction.run"
    >
      <div class="flex flex-wrap items-baseline gap-2">
        <Label for="bm-ask-limit" class="text-xs text-foreground">At most</Label>
        <Input
          id="bm-ask-limit"
          v-model="askLimit"
          type="number"
          min="1"
          placeholder="all"
          class="h-8 w-20"
        />
        <span class="text-xs text-muted-foreground flex-1 min-w-48">
          questions <strong class="text-foreground">per generator</strong> — built and asked. Blank
          takes all of them.
        </span>
      </div>

      <PhaseBlock
        title="Generate"
        help="Builds question/answer pairs from the corpus and screens them."
        v-model:open="sections.generate"
      >
        <details
          v-if="generatorKeys.length"
          class="group/generators"
          :open="sections.generators"
          @toggle="sections.generators = ($event.target as HTMLDetailsElement).open"
        >
          <summary
            class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
          >
            <ChevronRight
              class="h-3.5 w-3.5 transition-transform group-open/generators:rotate-90"
            />
            Generators ({{ enabledGeneratorCount }} of {{ generatorKeys.length }} enabled)
          </summary>
          <div class="pt-3 space-y-3">
            <GeneratorToggles
              v-model="disabledGenerators"
              :generators="generatorKeys"
              :inherited="inheritedDisabledGenerators"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>

        <details
          class="group/probe"
          :open="sections.probe"
          @toggle="sections.probe = ($event.target as HTMLDetailsElement).open"
        >
          <summary
            class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
          >
            <ChevronRight class="h-3.5 w-3.5 transition-transform group-open/probe:rotate-90" />
            Dataset settings
          </summary>
          <div class="pt-3 space-y-3">
            <LayerForm
              v-model="probeForm"
              :fields="fieldsFor('generate', 'probe')"
              :inherited="inheritedProbe"
              :connection-id="target?.connection_id ?? ''"
            />
            <LayerForm
              v-model="instrumentForm"
              :fields="fieldsFor('generate', 'instrument')"
              :inherited="inheritedInstrument"
              :connection-id="target?.connection_id ?? ''"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>
      </PhaseBlock>

      <PhaseBlock
        title="Filter"
        help="Its own screening is still to be written. Generate screens what it builds."
        v-model:open="sections.filter"
      >
        <p class="text-xs text-muted-foreground">Nothing here yet.</p>
      </PhaseBlock>

      <PhaseBlock
        title="Execute"
        help="Asks the active questions with these settings."
        v-model:open="sections.execute"
      >
        <LayerForm
          v-model="probeForm"
          :fields="fieldsFor('execute', 'probe')"
          :inherited="inheritedProbe"
          :connection-id="target?.connection_id ?? ''"
        />
        <LayerForm
          v-model="instrumentForm"
          :fields="fieldsFor('execute', 'instrument')"
          :inherited="inheritedInstrument"
          :connection-id="target?.connection_id ?? ''"
        />
        <Button size="sm" :disabled="saving" @click="persistTarget">
          {{ saving ? 'Saving…' : 'Save' }}
        </Button>
      </PhaseBlock>

      <PhaseBlock
        title="Judge"
        help="Grades the answers. Adds a verdict, never rewrites one."
        v-model:open="sections.judge"
      >
        <LayerForm
          v-model="instrumentForm"
          :fields="fieldsFor('judge', 'instrument')"
          :inherited="inheritedInstrument"
          :connection-id="target?.connection_id ?? ''"
        />
        <Button size="sm" :disabled="saving" @click="persistTarget">
          {{ saving ? 'Saving…' : 'Save' }}
        </Button>
        <p class="text-xs text-muted-foreground">
          Answers and verdicts are read on
          <strong class="text-foreground">Benchmark results</strong>, where the card is built and
          published. Only aggregates ever leave.
        </p>
      </PhaseBlock>
    </PhaseGroup>
  </section>
</template>

<script setup lang="ts">
/**
 * Measuring one endpoint, end to end: whether, when, and everything about
 * how — generate, filter, execute, judge, report — embedded here rather
 * than reached through a separate console.
 *
 * One launch, one button. The blocks below it hold the settings each phase
 * reads, and start nothing of their own: which phases a launch performs is
 * a property of the launch, not five separate starts that can each leave a
 * card measured on something other than what these settings say.
 *
 * Nothing on this page reads a result either: what a run produced is read on
 * the endpoint's Benchmark results tab, which is also where it is published.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { CheckCircle2, ChevronRight, Gauge, Play, TriangleAlert } from 'lucide-vue-next'

import { FIELD_PLACEMENT } from '@/components/benchmark/fieldPlacement'
import GeneratorToggles from '@/components/benchmark/GeneratorToggles.vue'
import LayerForm from '@/components/benchmark/LayerForm.vue'
import PhaseBlock from '@/components/benchmark/PhaseBlock.vue'
import PhaseGroup from '@/components/benchmark/PhaseGroup.vue'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { jobStateWords, useBenchmarkJobs } from '@/composables/useBenchmarkJobs'
import { usePersistedSections } from '@/composables/usePersistedSections'
import { apiErrorDetail } from '@/lib/errors'
import { formatTimeAgo } from '@/lib/formatters'
import type {
  BenchmarkCheck,
  BenchmarkField,
  BenchmarkJob,
  BenchmarkLayer,
  BenchmarkRunRequest,
  BenchmarkTarget,
} from '@/api/types'
import type { PhaseBlockKey } from '@/components/benchmark/fieldPlacement'

const props = defineProps<{ slug: string }>()

const router = useRouter()

// Which collapsible sections the owner left open, remembered per endpoint
// so a reload — or coming back tomorrow — does not fold everything again.
const sections = usePersistedSections(`benchmark-console:${props.slug}`, {
  settings: false,
  full: false,
  generate: false,
  generators: false,
  probe: false,
  filter: false,
  execute: false,
  judge: false,
})

const loading = ref(true)
const saving = ref(false)
const checking = ref(false)

const target = ref<BenchmarkTarget | null>(null)
const access = ref<BenchmarkCheck | null>(null)

const enabled = ref(true)
const collection = ref('')
const schedule = ref('')
const scheduleAt = ref('')
const probeForm = ref<BenchmarkLayer>({})
const instrumentForm = ref<BenchmarkLayer>({})

const hasBenchmark = computed(() => Boolean(target.value?.connection_id))

const inheritedProbe = computed<BenchmarkLayer>(() => ({
  ...target.value?.defaults?.probe,
  ...target.value?.connection_probe,
}))
const inheritedInstrument = computed<BenchmarkLayer>(() => ({
  ...target.value?.defaults?.instrument,
  ...target.value?.connection_instrument,
}))

// --- generators ------------------------------------------------------------

const generatorKeys = computed(() => target.value?.capabilities?.generators ?? [])

/** A layer's fields belonging to one phase block — see fieldPlacement.ts. */
function fieldsFor(block: PhaseBlockKey, layer: 'probe' | 'instrument'): BenchmarkField[] {
  const names: readonly string[] = FIELD_PLACEMENT[block][layer]
  const all = target.value?.fields[layer] ?? []
  return all.filter((field) => names.includes(field.name))
}

const disabledGenerators = computed<string[] | undefined>({
  get: () => probeForm.value.disabled_generators as string[] | undefined,
  set: (value) => {
    const out = { ...probeForm.value }
    if (value === undefined) delete out.disabled_generators
    else out.disabled_generators = value
    probeForm.value = out
  },
})

const inheritedDisabledGenerators = computed<string[] | undefined>(
  () => inheritedProbe.value.disabled_generators as string[] | undefined,
)

const enabledGeneratorCount = computed(() => {
  const off = new Set(disabledGenerators.value ?? inheritedDisabledGenerators.value ?? [])
  return generatorKeys.value.filter((key) => !off.has(key)).length
})

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

async function load() {
  try {
    const fresh = await benchmarksApi.getTarget(props.slug)
    target.value = fresh
    enabled.value = fresh.enabled
    collection.value = fresh.collection
    schedule.value = fresh.schedule
    scheduleAt.value = fresh.schedule_at
    probeForm.value = { ...fresh.probe }
    instrumentForm.value = { ...fresh.instrument }
  } catch {
    toast.error('Could not read the benchmark settings for this endpoint')
  } finally {
    loading.value = false
  }
}

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

async function persistTarget() {
  saving.value = true
  try {
    target.value = await benchmarksApi.saveTarget(props.slug, {
      enabled: enabled.value,
      collection: collection.value,
      probe: probeForm.value,
      instrument: instrumentForm.value,
      schedule: schedule.value,
      // The hour only means anything to a daily interval; sending it with a
      // six-hourly one would leave a value in the form that decides nothing.
      schedule_at: schedule.value === '24h' ? scheduleAt.value : '',
    })
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

const accessTone = computed(() =>
  access.value?.ok
    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
    : 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
)

function ago(stamp: string | null): string {
  return stamp ? formatTimeAgo(stamp) : ''
}

// --- the phases -----------------------------------------------------------

const { jobs, running, refresh: refreshJobs } = useBenchmarkJobs(props.slug)

// The latest job of a kind is not this page's job: a schedule fires the same
// kind, and the benchmark leaves `phase` at `done` once any of them finishes,
// so a finished job cannot say afterwards who started it. So the button
// remembers the id of the launch IT started and reads that one back out of
// the poll.
const startedJobId = ref<string>('')

const fullJob = computed(() =>
  startedJobId.value ? jobs.value.find((job) => job.id === startedJobId.value) : undefined,
)

function progressOf(job: BenchmarkJob | undefined): number | 'indeterminate' | null {
  if (!job || job.state !== 'running') return null
  // The finer of the two counters wins: `step_total` is a count of
  // questions within whatever is running now (a pass, a judging batch),
  // and moves continuously, where `total` only moves once a whole pass
  // ends. Generation and filtering report neither — "running with no
  // total" still means something is happening, just not how far along.
  if (job.step_total) return Math.round((job.step_done / job.step_total) * 100)
  if (!job.total) return 'indeterminate'
  return Math.round((job.done / job.total) * 100)
}

/**
 * How many questions a launch asks of each generator.
 *
 * Deliberately not a saved setting and deliberately not remembered across a
 * reload: it belongs to one launch. A cap left lying about in the settings is
 * the kind of thing that quietly makes every nightly measurement a sample of
 * four questions, and the figures would not look wrong — only thin.
 */
const askLimit = ref('')

/** The cap as the benchmark takes it: a whole number of at least one, or nothing. */
const askLimitBody = computed<{ limit?: number }>(() => {
  const asked = Math.floor(Number(askLimit.value))
  return Number.isFinite(asked) && asked >= 1 ? { limit: asked } : {}
})

const acting = ref(false)

async function act(fn: () => Promise<BenchmarkJob>): Promise<void> {
  acting.value = true
  try {
    startedJobId.value = (await fn()).id
    await refreshJobs()
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not start this run'))
  } finally {
    acting.value = false
  }
}

const busy = computed(() => acting.value || running.value)

function startRun(body: BenchmarkRunRequest) {
  return benchmarksApi.startRun(props.slug, body)
}

// --- stopping a run in progress ---------------------------------------------

function isActive(job: BenchmarkJob | undefined): boolean {
  return job?.state === 'queued' || job?.state === 'running'
}

const cancellingId = ref<string | null>(null)

async function cancelJob(job: BenchmarkJob | undefined): Promise<void> {
  if (!job) return
  cancellingId.value = job.id
  try {
    await benchmarksApi.cancelRun(props.slug, job.id)
    await refreshJobs()
    toast.success('Stopping — it finishes the question it is on, then exits')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not stop this run'))
  } finally {
    cancellingId.value = null
  }
}

/**
 * The whole thing in one launch: build the questions, screen them, ask them,
 * grade them, write the card.
 *
 * "Run" while nothing is in flight, "Cancel" in its place once something is —
 * a second launch is refused by the queue anyway, so the button that would
 * have started one becomes the one thing still useful.
 *
 * The cap applies to both halves — two questions per generator built, those
 * two asked — so a configuration can be tried end to end for the price of a
 * handful of calls.
 */
const fullAction = computed(() => {
  const job = fullJob.value
  if (isActive(job)) {
    return {
      label: 'Cancel',
      disabled: cancellingId.value === job?.id,
      destructive: true,
      run: () => cancelJob(job),
    }
  }
  return {
    label: 'Run',
    disabled: busy.value,
    destructive: false,
    run: () => act(() => startRun({ generate: true, evaluate: true, ...askLimitBody.value })),
  }
})

onMounted(load)
</script>
