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
              <template v-else>
                Nothing runs on a schedule. Start a phase below by hand.
              </template>
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
      title="Preparation"
      status="Generation, then filtering"
      :action-label="preparationAction.label"
      :action-disabled="preparationAction.disabled"
      :action-destructive="preparationAction.destructive"
      v-model:open="sections.preparation"
      @action="preparationAction.run"
    >
      <PhaseBlock
        title="Generation"
        help="Builds new question/answer pairs from the corpus. Everything it builds lands pending — nothing here decides whether a pair is any good, that is Filtering's job."
        :status="jobStateWords(generationJob)"
        :progress="progressOf(generationJob)"
        :action-label="generationAction.label"
        :action-disabled="generationAction.disabled"
        :action-destructive="generationAction.destructive"
        v-model:open="sections.generation"
        @action="generationAction.run"
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
            <ChevronRight class="h-3.5 w-3.5 transition-transform group-open/generators:rotate-90" />
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
              :fields="fieldsFor('generation', 'probe')"
              :inherited="inheritedProbe"
              :connection-id="target?.connection_id ?? ''"
            />
            <LayerForm
              v-model="instrumentForm"
              :fields="fieldsFor('generation', 'instrument')"
              :inherited="inheritedInstrument"
              :connection-id="target?.connection_id ?? ''"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>
        <PairList :slug="props.slug" :refresh-key="refreshKey" :generators="generatorKeys" />
      </PhaseBlock>

      <PhaseBlock
        title="Filtering"
        help="Screens pending pairs for grounding and, for control items, checks live retrieval again. Only pending pairs are touched automatically — overturn a verdict by hand below."
        :status="jobStateWords(filterJob)"
        :progress="progressOf(filterJob)"
        :action-label="filteringAction.label"
        :action-disabled="filteringAction.disabled"
        :action-destructive="filteringAction.destructive"
        v-model:open="sections.filtering"
        @action="filteringAction.run"
      >
        <details
          v-if="fieldsFor('filtering', 'instrument').length"
          class="group/filterset"
          :open="sections.filteringSettings"
          @toggle="sections.filteringSettings = ($event.target as HTMLDetailsElement).open"
        >
          <summary
            class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
          >
            <ChevronRight
              class="h-3.5 w-3.5 transition-transform group-open/filterset:rotate-90"
            />
            Filtering settings
          </summary>
          <div class="pt-3 space-y-3">
            <LayerForm
              v-model="instrumentForm"
              :fields="fieldsFor('filtering', 'instrument')"
              :inherited="inheritedInstrument"
              :connection-id="target?.connection_id ?? ''"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>
        <PairList
          :slug="props.slug"
          status="pending"
          :refresh-key="refreshKey"
          :generators="generatorKeys"
        />
      </PhaseBlock>
    </PhaseGroup>

    <PhaseGroup
      title="Testing"
      status="Execution, judging and the report"
      :action-label="testingAction.label"
      :action-disabled="testingAction.disabled"
      :action-destructive="testingAction.destructive"
      v-model:open="sections.testing"
      @action="testingAction.run"
    >
      <PhaseBlock
        title="Execution"
        help="Asks the active questions. Run on its own, it defers judging so the Judging block has pending verdicts to grade — Testing above grades inline instead."
        :status="jobStateWords(executionJob)"
        :progress="progressOf(executionJob)"
        :action-label="executionAction.label"
        :action-disabled="executionAction.disabled"
        :action-destructive="executionAction.destructive"
        v-model:open="sections.execution"
        @action="executionAction.run"
      >
        <details
          class="group/instrument"
          :open="sections.instrument"
          @toggle="sections.instrument = ($event.target as HTMLDetailsElement).open"
        >
          <summary
            class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
          >
            <ChevronRight class="h-3.5 w-3.5 transition-transform group-open/instrument:rotate-90" />
            Execution settings
          </summary>
          <div class="pt-3 space-y-3">
            <LayerForm
              v-model="probeForm"
              :fields="fieldsFor('execution', 'probe')"
              :inherited="inheritedProbe"
              :connection-id="target?.connection_id ?? ''"
            />
            <LayerForm
              v-model="instrumentForm"
              :fields="fieldsFor('execution', 'instrument')"
              :inherited="inheritedInstrument"
              :connection-id="target?.connection_id ?? ''"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>
        <p class="text-xs text-muted-foreground">
          Answers are graded in the Judging block below, or reviewed on the target's published card
          once Testing has run.
        </p>
        <ResultList :slug="props.slug" :refresh-key="refreshKey" :generators="generatorKeys" />
      </PhaseBlock>

      <PhaseBlock
        title="Judging"
        help="Grades pending verdicts — the ones Execution left ungraded. Never rewrites a verdict, only adds a new one; every reader already takes the freshest."
        :status="jobStateWords(judgeJob)"
        :progress="progressOf(judgeJob)"
        :action-label="judgingAction.label"
        :action-disabled="judgingAction.disabled"
        :action-destructive="judgingAction.destructive"
        v-model:open="sections.judging"
        @action="judgingAction.run"
      >
        <details
          v-if="fieldsFor('judging', 'instrument').length"
          class="group/judgeset"
          :open="sections.judgingSettings"
          @toggle="sections.judgingSettings = ($event.target as HTMLDetailsElement).open"
        >
          <summary
            class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
          >
            <ChevronRight
              class="h-3.5 w-3.5 transition-transform group-open/judgeset:rotate-90"
            />
            Judging settings
          </summary>
          <div class="pt-3 space-y-3">
            <LayerForm
              v-model="instrumentForm"
              :fields="fieldsFor('judging', 'instrument')"
              :inherited="inheritedInstrument"
              :connection-id="target?.connection_id ?? ''"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>
        <ResultList :slug="props.slug" :refresh-key="refreshKey" :generators="generatorKeys" />
      </PhaseBlock>

      <PhaseBlock
        title="Report"
        help="Builds the card from what is active and graded right now — no fresh run needed. Publishing is a separate, explicit step."
        status=""
        action-label="Build"
        :action-disabled="reportLoading"
        v-model:open="sections.report"
        @action="doBuildReport"
      >
        <details
          v-if="fieldsFor('report', 'instrument').length"
          class="group/reportset"
          :open="sections.reportSettings"
          @toggle="sections.reportSettings = ($event.target as HTMLDetailsElement).open"
        >
          <summary
            class="text-xs font-medium text-foreground cursor-pointer select-none flex items-center gap-1.5"
          >
            <ChevronRight
              class="h-3.5 w-3.5 transition-transform group-open/reportset:rotate-90"
            />
            Report settings
          </summary>
          <div class="pt-3 space-y-3">
            <LayerForm
              v-model="instrumentForm"
              :fields="fieldsFor('report', 'instrument')"
              :inherited="inheritedInstrument"
              :connection-id="target?.connection_id ?? ''"
            />
            <Button size="sm" :disabled="saving" @click="persistTarget">
              {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </div>
        </details>
        <div v-if="report" class="space-y-4">
          <ReportView :report="report" />
          <div class="flex gap-2">
            <Button size="sm" :disabled="reportLoading" @click="doPublish">Publish</Button>
            <Button variant="outline" size="sm" :disabled="reportLoading" @click="doRetract">
              Retract
            </Button>
          </div>
          <p class="text-xs text-muted-foreground">
            Publishing sends only the aggregates above to the hub card — never a question, an
            answer or corpus text.
          </p>
        </div>
        <p v-else class="text-sm text-muted-foreground">Not built yet.</p>
      </PhaseBlock>
    </PhaseGroup>
  </section>
</template>

<script setup lang="ts">
/**
 * Measuring one endpoint, end to end: whether, when, and everything about
 * how — generation, filtering, execution, judging, the report — embedded
 * here rather than reached through a separate console.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { CheckCircle2, ChevronRight, Gauge, Play, TriangleAlert } from 'lucide-vue-next'

import { FIELD_PLACEMENT } from '@/components/benchmark/fieldPlacement'
import GeneratorToggles from '@/components/benchmark/GeneratorToggles.vue'
import LayerForm from '@/components/benchmark/LayerForm.vue'
import PairList from '@/components/benchmark/PairList.vue'
import PhaseBlock from '@/components/benchmark/PhaseBlock.vue'
import PhaseGroup from '@/components/benchmark/PhaseGroup.vue'
import ReportView from '@/components/benchmark/ReportView.vue'
import ResultList from '@/components/benchmark/ResultList.vue'
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
  BenchmarkReport,
  BenchmarkRunRequest,
  BenchmarkTarget,
} from '@/api/types'
import type { PhaseBlockKey } from '@/components/benchmark/fieldPlacement'

const props = defineProps<{ slug: string }>()
const emit = defineEmits<{ 'card-changed': [] }>()

const router = useRouter()

// Which collapsible sections the owner left open, remembered per endpoint
// so a reload — or coming back tomorrow — does not fold everything again.
const sections = usePersistedSections(`benchmark-console:${props.slug}`, {
  settings: false,
  preparation: false,
  generation: false,
  generators: false,
  probe: false,
  filtering: false,
  filteringSettings: false,
  testing: false,
  execution: false,
  instrument: false,
  judging: false,
  judgingSettings: false,
  report: false,
  reportSettings: false,
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

const { jobs, running, refresh: refreshJobs, latestOf } = useBenchmarkJobs(props.slug)

// Bumped so PairList/ResultList reload without each of them polling the job
// queue on their own — on every poll while something is running, since
// generation and filtering write pairs one at a time as they go and the
// owner watching Generation should see them appear rather than wait for the
// whole pass to end; and once more on the exact tick a job finishes, in case
// the last poll landed a beat before its final row.
const refreshKey = ref(0)
const seenFinal = new Set<string>()
watch(
  jobs,
  (current) => {
    let sawFinal = false
    for (const job of current) {
      const final = job.state === 'succeeded' || job.state === 'failed' || job.state === 'cancelled'
      if (final && !seenFinal.has(job.id)) {
        seenFinal.add(job.id)
        sawFinal = true
      }
    }
    if (sawFinal || running.value) {
      refreshKey.value += 1
    }
  },
  { deep: true },
)

// `kind` alone cannot tell a generation-only pipeline job from an
// execution-only one — both are `pipeline`, and the benchmark leaves
// `phase` at `done` once either finishes, so a job's own fields cannot
// say afterwards which block started it either. So each block that can
// start a `pipeline` job remembers the id of the one IT started, and reads
// that job's current state back out of the poll — rather than the latest
// job of its kind, which might belong to a different block entirely.
const startedJobId = ref<Record<string, string>>({})

function jobFor(name: string): BenchmarkJob | undefined {
  const id = startedJobId.value[name]
  return id ? jobs.value.find((job) => job.id === id) : undefined
}

const preparationJob = computed(() => jobFor('preparation'))
const generationJob = computed(() => jobFor('generation'))
const testingJob = computed(() => jobFor('testing'))
const executionJob = computed(() => jobFor('execution'))
const filterJob = computed(() => latestOf('filter'))
const judgeJob = computed(() => latestOf('judge'))

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

const acting = ref<string | null>(null)

async function act(name: string, fn: () => Promise<BenchmarkJob>): Promise<void> {
  acting.value = name
  try {
    const job = await fn()
    startedJobId.value[name] = job.id
    await refreshJobs()
  } catch (error) {
    toast.error(apiErrorDetail(error, `Could not start ${name}`))
  } finally {
    acting.value = null
  }
}

const busy = computed(() => acting.value !== null || running.value)

function startRun(body: BenchmarkRunRequest) {
  return benchmarksApi.startRun(props.slug, body)
}

function runFilter() {
  return benchmarksApi.runFilter(props.slug)
}

function runJudge() {
  return benchmarksApi.runJudge(props.slug)
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
 * The run button for one block: "Run" (or the given label) while nothing of
 * its own is in flight, "Cancel" in its place once something is — starting a
 * second run while one is already going is refused by the queue anyway, so
 * the button that would have done that becomes the one thing still useful:
 * stopping the one that is running.
 */
function actionFor(
  job: BenchmarkJob | undefined,
  startLabel: string,
  start: () => Promise<unknown>,
) {
  if (isActive(job)) {
    return {
      label: 'Cancel',
      disabled: cancellingId.value === job?.id,
      destructive: true,
      run: () => cancelJob(job),
    }
  }
  return {
    label: startLabel,
    disabled: busy.value,
    destructive: false,
    run: start,
  }
}

const preparationAction = computed(() =>
  actionFor(preparationJob.value, 'Run preparation', () =>
    act('preparation', () => startRun({ generate: true, evaluate: false })),
  ),
)
const generationAction = computed(() =>
  actionFor(generationJob.value, 'Run', () =>
    act('generation', () => startRun({ generate: true, evaluate: false, filter: false })),
  ),
)
const filteringAction = computed(() =>
  actionFor(filterJob.value, 'Run', () => act('filter', () => runFilter())),
)
const testingAction = computed(() =>
  actionFor(testingJob.value, 'Run testing', () =>
    act('testing', () => startRun({ generate: false, evaluate: true })),
  ),
)
const executionAction = computed(() =>
  actionFor(executionJob.value, 'Run', () =>
    act('execution', () =>
      startRun({ generate: false, evaluate: true, defer_judging: true, publish: false }),
    ),
  ),
)
const judgingAction = computed(() =>
  actionFor(judgeJob.value, 'Run', () => act('judge', () => runJudge())),
)

// Report state, rebuilt on demand rather than polled: it is a fast,
// synchronous call, not a queued job — and never stored, so it is gone
// after a reload unless something loads it back.
const report = ref<BenchmarkReport | null>(null)
const reportLoading = ref(false)

async function doBuildReport(): Promise<void> {
  reportLoading.value = true
  try {
    report.value = await benchmarksApi.buildReport(props.slug)
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not build the report'))
  } finally {
    reportLoading.value = false
  }
}

/**
 * The same rebuild, run quietly on load: an endpoint with nothing gradable
 * yet answers 409, which is the ordinary state of a page nobody has
 * measured, not a failure worth a toast over.
 */
async function loadReport(): Promise<void> {
  try {
    report.value = await benchmarksApi.buildReport(props.slug)
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    if (status !== 409) toast.error(apiErrorDetail(error, 'Could not load the report'))
  }
}

async function doPublish(): Promise<void> {
  reportLoading.value = true
  try {
    report.value = await benchmarksApi.publishReport(props.slug)
    toast.success('Published')
    emit('card-changed')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not publish'))
  } finally {
    reportLoading.value = false
  }
}

async function doRetract(): Promise<void> {
  reportLoading.value = true
  try {
    await benchmarksApi.retractReport(props.slug)
    toast.success('Retracted')
    emit('card-changed')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not retract'))
  } finally {
    reportLoading.value = false
  }
}

onMounted(async () => {
  await load()
  if (hasBenchmark.value) await loadReport()
})
</script>
