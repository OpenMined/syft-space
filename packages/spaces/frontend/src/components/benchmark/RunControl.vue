<template>
  <div v-if="loading" class="space-y-3">
    <Skeleton class="h-28 w-full" />
  </div>

  <!-- No benchmark is wired to this Space, or this endpoint is not opted in. -->
  <section
    v-else-if="!target?.connection_id && !target?.measured"
    class="rounded-lg border border-border/50 p-6 text-center"
  >
    <Gauge class="mx-auto mb-3 h-7 w-7 text-muted-foreground/50" />
    <h3 class="mb-1 text-sm font-medium text-foreground">
      {{ hasBenchmark ? 'This endpoint is not measured' : 'No benchmark is connected' }}
    </h3>
    <p class="mx-auto mb-4 max-w-md text-xs text-muted-foreground">
      <template v-if="hasBenchmark">
        Nothing is grading this endpoint yet. Turn it on to set up the benchmark.
      </template>
      <template v-else>
        Measuring is a separate service, and this Space is not wired to one yet.
      </template>
    </p>
    <Button v-if="hasBenchmark" size="sm" :disabled="saving" @click="startMeasuring">
      <Play class="mr-1.5 h-4 w-4" />
      Measure this endpoint
    </Button>
    <Button v-else size="sm" variant="outline" @click="router.push({ name: 'model-access' })">
      Connect a benchmark
    </Button>
  </section>

  <!-- Negative bottom margin keeps the bottom bar flush with the page. -->
  <div
    v-else-if="target && form"
    class="-mb-10 flex flex-col gap-6 lg:-mb-12"
    data-testid="benchmark-setup"
  >
    <div class="space-y-0.5">
      <h1 class="text-xl font-semibold text-foreground">Benchmark setup</h1>
      <p class="max-w-[780px] text-sm text-muted-foreground">
        How we measure what your reporting adds to AI models. Every run follows the five steps
        below.
      </p>
    </div>

    <div
      v-if="activeJob"
      class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-primary bg-primary/5 px-3.5 py-2.5 text-sm text-primary"
    >
      <b class="font-semibold">A run is in progress</b>
      <span>Settings are locked until it finishes.</span>
    </div>
    <div
      v-else-if="lastRun"
      class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-muted/30 px-3.5 py-2.5 text-sm"
      data-testid="last-run"
    >
      <span>
        <span class="text-muted-foreground">Last run</span> ·
        {{ dayTime(utcStamp(lastRun.created_at)) }} ·
        {{ plural(lastRun.questions ?? 0, 'question') }} ·
        {{ plural(lastRun.models.length, 'model') }}
      </span>
      <RouterLink
        :to="runLocation(lastRun.job_id)"
        class="font-medium text-primary hover:underline"
      >
        See its results
      </RouterLink>
    </div>

    <div
      v-if="!target.enabled"
      class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 px-3.5 py-2.5 text-sm"
    >
      <span>Measuring is stopped for this endpoint. Settings and past runs are kept.</span>
      <Button size="sm" variant="outline" :disabled="saving || locked" @click="setMeasuring(true)">
        Resume measuring
      </Button>
    </div>

    <fieldset :disabled="locked" class="m-0 flex min-w-0 flex-col gap-4 border-0 p-0">
      <legend class="sr-only">Benchmark settings</legend>

      <ArticlesStep
        v-model:form="form"
        :dataset="dataset"
        :articles="articles"
        :resolved-collection="target.resolved_collection"
      />
      <WriteStep v-model:form="form" :connection-id="connectionId" :kinds="kinds" />
      <WebCheckStep
        v-model:form="form"
        :connection-id="connectionId"
        :judge-one-label="judgeOneLabel"
      />
      <AskStep
        v-model:form="form"
        :connection-id="connectionId"
        :skipped-names="skippedRepeats.map(nameOf)"
      />
      <GradeStep v-model:form="form" :connection-id="connectionId" :judge-slots="judgeSlots" />
      <RunSettings
        v-model:form="form"
        :enabled="target.enabled"
        :saving="saving"
        @stop-measuring="setMeasuring(false)"
      />
    </fieldset>

    <div
      class="sticky bottom-0 z-10 -mx-4 border-t border-border bg-background px-4 py-3.5 shadow-[0_-4px_12px_rgba(5,8,11,0.04)] sm:-mx-6 sm:px-6"
      data-testid="run-bar"
    >
      <RunProgress
        v-if="activeJob"
        :job="activeJob"
        :cancelling="cancelling"
        :name-of="nameOf"
        @stop="stopRun"
      />

      <template v-else>
        <ClashPanel
          v-if="clashes.length"
          :clashes="clashes"
          :blocked="blocked"
          :name-of="nameOf"
          @remove-model="removeModel"
        />

        <div class="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div class="flex min-w-0 flex-col gap-0.5">
            <span class="font-medium">Run with these settings</span>
            <span class="text-[13px] text-muted-foreground" data-testid="run-summary">
              {{ summary }}
            </span>
            <span
              class="text-xs"
              :class="statusWarn ? 'text-amber-800 dark:text-amber-300' : 'text-muted-foreground'"
            >
              {{ statusText }}
            </span>
            <span
              v-if="error"
              role="alert"
              class="text-xs text-destructive"
              data-testid="bar-error"
            >
              {{ error }}
            </span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Button v-if="dirty" variant="ghost" :disabled="saving || acting" @click="discard">
              Discard changes
            </Button>
            <Button variant="outline" size="lg" :disabled="!canSave" @click="save">
              {{ saving && !acting ? 'Saving…' : 'Save without running' }}
            </Button>
            <Button size="lg" :disabled="!canRun" data-testid="run-button" @click="run">
              {{
                acting ? 'Starting…' : clashes.length && !blocked ? 'Run anyway' : 'Run benchmark'
              }}
            </Button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * The endpoint's Benchmark setup tab: five steps that follow the pipeline, one save
 * and one Run button. The page shows effective values (the endpoint's own
 * layer, else the connection's, else the benchmark's defaults); the rules that
 * turn them into a request live in setup/setupForm.ts.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { Gauge, Play } from 'lucide-vue-next'

import { KINDS } from '@/components/benchmark/kinds'
import { plural } from '@/components/benchmark/labels'
import { dayTime, utcStamp } from '@/components/benchmark/report/figures'
import { modelName } from '@/components/benchmark/report/labels'
import { runLocation } from '@/components/benchmark/report/routing'
import ArticlesStep from '@/components/benchmark/setup/ArticlesStep.vue'
import AskStep from '@/components/benchmark/setup/AskStep.vue'
import ClashPanel from '@/components/benchmark/setup/ClashPanel.vue'
import GradeStep from '@/components/benchmark/setup/GradeStep.vue'
import RunProgress from '@/components/benchmark/setup/RunProgress.vue'
import RunSettings from '@/components/benchmark/setup/RunSettings.vue'
import WebCheckStep from '@/components/benchmark/setup/WebCheckStep.vue'
import WriteStep from '@/components/benchmark/setup/WriteStep.vue'
import { findClashes, monteCarloSkipped } from '@/components/benchmark/setup/models'
import {
  buildRequest,
  formFromTarget,
  problemsOf,
  runProblemsOf,
  runSummary,
  sameRequest,
  storedRequest,
} from '@/components/benchmark/setup/setupForm'
import type { JudgeSlot, SetupForm } from '@/components/benchmark/setup/setupForm'
import { useArticleWindow } from '@/components/benchmark/setup/useArticleWindow'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { useBenchmarkJobs } from '@/composables/useBenchmarkJobs'
import { useModelCatalog } from '@/composables/useModelCatalog'
import { apiErrorDetail } from '@/lib/errors'
import type { BenchmarkRunSummary, BenchmarkTarget, BenchmarkTargetRequest } from '@/api/types'

const props = withDefaults(
  defineProps<{ slug: string; dataset?: { name: string; dtype: string } | null }>(),
  { dataset: null },
)

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const acting = ref(false)
const cancelling = ref(false)
const error = ref('')

const target = ref<BenchmarkTarget | null>(null)
const form = ref<SetupForm | null>(null)
const lastRun = ref<BenchmarkRunSummary | null>(null)

const hasBenchmark = computed(() => Boolean(target.value?.connection_id))
const connectionId = computed(() => target.value?.connection_id ?? '')

const { articles, reload: loadWindow } = useArticleWindow(props.slug, () => form.value?.windowDays)

// --- models and judges -------------------------------------------------------

const { catalog, load: loadCatalog } = useModelCatalog()
const byId = computed(() => new Map(catalog.value.models.map((m) => [m.id, m])))

function nameOf(id: string): string {
  return modelName(id, byId.value.get(id))
}

watch(connectionId, (id) => id && void loadCatalog(id), { immediate: true })

const kinds = computed<string[]>(() => {
  const offered = target.value?.capabilities?.generators
  return offered?.length ? offered : KINDS.map((kind) => kind.key)
})

const countedJudges = computed(() =>
  form.value ? form.value.judges.slice(0, form.value.judgeCount) : [],
)

const clashes = computed(() =>
  form.value
    ? findClashes(countedJudges.value, form.value.models, (id) => byId.value.get(id)?.vendor)
    : [],
)

const judgeSlots = computed<JudgeSlot[]>(() =>
  countedJudges.value.map((id, index) => ({
    index,
    id,
    exclude: countedJudges.value.filter((other, at) => at !== index && other),
    clashWith: clashes.value.filter((c) => c.judge === index).map((c) => nameOf(c.model)),
  })),
)

const judgeOneLabel = computed(() => {
  const first = form.value?.judges[0]
  return first ? `Judge 1 · ${nameOf(first)}` : 'Judge 1'
})

const blocked = computed(() => clashes.value.length > 0 && form.value?.judgePolicy !== 'warn')

const skippedRepeats = computed(() =>
  form.value ? monteCarloSkipped(form.value, (id) => byId.value.get(id)) : [],
)

function removeModel(id: string): void {
  if (!form.value) return
  form.value.models = form.value.models.filter((model) => model !== id)
}

// --- the run bar's state ---------------------------------------------------------

const { jobs, refresh: refreshJobs } = useBenchmarkJobs(props.slug)

const activeJob = computed(() =>
  jobs.value.find((job) => job.state === 'queued' || job.state === 'running'),
)

const request = computed<BenchmarkTargetRequest | null>(() =>
  target.value && form.value ? buildRequest(target.value, form.value, kinds.value) : null,
)

const dirty = computed(
  () =>
    !!target.value && !!request.value && !sameRequest(request.value, storedRequest(target.value)),
)

const problems = computed(() => (form.value ? problemsOf(form.value, kinds.value) : []))
const runProblems = computed(() => (form.value ? runProblemsOf(form.value) : []))

const locked = computed(() => Boolean(activeJob.value) || acting.value)

const canSave = computed(
  () => dirty.value && !blocked.value && !problems.value.length && !locked.value && !saving.value,
)

const canRun = computed(
  () =>
    !blocked.value &&
    !problems.value.length &&
    !runProblems.value.length &&
    !locked.value &&
    !saving.value &&
    Boolean(target.value?.enabled),
)

const summary = computed(() =>
  form.value ? runSummary(form.value, articles.value, skippedRepeats.value.map(nameOf)) : '',
)

const statusWarn = computed(
  () =>
    blocked.value ||
    problems.value.length > 0 ||
    runProblems.value.length > 0 ||
    dirty.value ||
    !target.value?.enabled,
)

const statusText = computed(() => {
  if (blocked.value) return 'Fix the conflict above to save or run.'
  if (problems.value.length) return problems.value.join(' ')
  if (!target.value?.enabled) return 'Measuring is stopped. Resume it above to run.'
  if (runProblems.value.length) return runProblems.value.join(' ')
  if (dirty.value) return 'You have unsaved changes. Running saves them first.'
  return 'All settings saved.'
})

// --- loading, saving and running ---------------------------------------------------

function adopt(fresh: BenchmarkTarget): void {
  target.value = fresh
  form.value = formFromTarget(fresh, kinds.value)
}

async function load(): Promise<void> {
  try {
    adopt(await benchmarksApi.getTarget(props.slug))
  } catch {
    toast.error('Could not read the benchmark settings for this endpoint')
  } finally {
    loading.value = false
  }
}

async function loadLastRun(): Promise<void> {
  try {
    const list = await benchmarksApi.listReportRuns(props.slug, { limit: 1 })
    lastRun.value = list.items[0] ?? null
  } catch {
    lastRun.value = null
  }
}

/** The one save. Returns false when the benchmark refused it. */
async function persist(): Promise<boolean> {
  if (!target.value || !request.value) return false
  saving.value = true
  error.value = ''
  try {
    adopt(await benchmarksApi.saveTarget(props.slug, request.value))
    return true
  } catch (err) {
    error.value = apiErrorDetail(err, 'Could not save')
    toast.error(error.value)
    return false
  } finally {
    saving.value = false
  }
}

async function save(): Promise<void> {
  if (canSave.value && (await persist())) toast.success('Saved')
}

function discard(): void {
  if (target.value) form.value = formFromTarget(target.value, kinds.value)
  error.value = ''
}

async function run(): Promise<void> {
  if (!canRun.value) return
  acting.value = true
  error.value = ''
  try {
    if (dirty.value && !(await persist())) return
    await benchmarksApi.startRun(props.slug, { generate: true, evaluate: true })
    await refreshJobs()
  } catch (err) {
    error.value = apiErrorDetail(err, 'Could not start this run')
    toast.error(error.value)
  } finally {
    acting.value = false
  }
}

async function setMeasuring(on: boolean): Promise<void> {
  if (!target.value) return
  saving.value = true
  error.value = ''
  try {
    adopt(
      await benchmarksApi.saveTarget(props.slug, { ...storedRequest(target.value), enabled: on }),
    )
    toast.success(on ? 'Measuring resumed' : 'Measuring stopped. Settings and past runs are kept.')
  } catch (err) {
    error.value = apiErrorDetail(err, 'Could not change this')
    toast.error(error.value)
  } finally {
    saving.value = false
  }
}

async function startMeasuring(): Promise<void> {
  saving.value = true
  try {
    await benchmarksApi.saveTarget(props.slug, { enabled: true, probe: {} })
    await load()
    toast.success('This endpoint is now measured')
  } catch (err) {
    toast.error(apiErrorDetail(err, 'Could not start measuring this endpoint'))
  } finally {
    saving.value = false
  }
}

async function stopRun(): Promise<void> {
  const job = activeJob.value
  if (!job) return
  cancelling.value = true
  try {
    await benchmarksApi.cancelRun(props.slug, job.id)
    await refreshJobs()
    toast.success('Stopping — it finishes the question it is on, then exits')
  } catch (err) {
    toast.error(apiErrorDetail(err, 'Could not stop this run'))
  } finally {
    cancelling.value = false
  }
}

// Reload after a run finishes.
watch(
  () => activeJob.value?.id,
  (now, before) => {
    if (before && !now) {
      void loadLastRun()
      void loadWindow()
    }
  },
)

onMounted(() => {
  void load()
  void loadLastRun()
  void loadWindow()
})
</script>
