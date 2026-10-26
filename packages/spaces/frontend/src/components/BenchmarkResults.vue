<script setup lang="ts">
/**
 * The technical view: every run of this endpoint as a card, newest first and open.
 * Finished jobs show their stored card; the newest measuring run shows a live rebuild.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronRight, FlaskConical } from 'lucide-vue-next'

import RunCard from '@/components/benchmark/RunCard.vue'
import RunDetail from '@/components/benchmark/RunDetail.vue'
import { buildText } from '@/components/benchmark/filter'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type {
  BenchmarkCard,
  BenchmarkJob,
  BenchmarkReport,
  BenchmarkRunSummary,
} from '@/api/types'

const props = defineProps<{ slug: string }>()

const route = useRoute()
const router = useRouter()

const loading = ref(true)
/** Jobs as the benchmark lists them; the finished ones carry their card. */
const jobs = ref<BenchmarkJob[]>([])
/** Jobs that wrote or filtered questions but asked no model. */
const buildOnly = ref<BenchmarkRunSummary[]>([])

/** The card built from what is graded right now, for the newest measuring run. */
const latest = ref<BenchmarkReport | null>(null)

/** A stamp parsed as UTC when it carries no zone. */
function moment(value: string | null | undefined): Date | null {
  if (!value) return null
  const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const parsed = new Date(zoned)
  return Number.isNaN(parsed.valueOf()) ? null : parsed
}

function formatMoment(value: string | null | undefined): string {
  const at = moment(value)
  if (!at) return '—'
  return at.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface RunView {
  key: string
  /** Null for a build-only job. */
  card: BenchmarkCard | BenchmarkReport | null
  jobId?: string
  build?: string | null
  measured: string
  at: number
}

function cardRun(key: string, card: BenchmarkCard | BenchmarkReport, jobId?: string): RunView {
  return {
    key,
    card,
    jobId,
    measured: formatMoment(card.checked_at),
    at: moment(card.checked_at)?.valueOf() ?? 0,
  }
}

const runs = computed<RunView[]>(() => {
  const build = latest.value
  const list: RunView[] = []
  let latestShown = false

  for (const job of jobs.value) {
    if (!job.card) continue
    // The live build replaces the stored card of the run it is of.
    const live = build && build.job && build.job === job.id ? build : null
    if (live) latestShown = true
    list.push(cardRun(job.id, live ?? job.card, job.id))
  }

  // A build no listed job owns: a run from the CLI, or one older than the list.
  if (build && !latestShown) {
    const at = moment(build.checked_at)?.valueOf() ?? 0
    if (!list.some((run) => Math.abs(run.at - at) < 1000)) {
      list.push(cardRun('latest', build, build.job || undefined))
    }
  }

  for (const job of buildOnly.value) {
    list.push({
      key: `job-${job.job_id}`,
      card: null,
      jobId: job.job_id,
      build: buildText(job.build),
      measured: formatMoment(job.created_at),
      at: moment(job.created_at)?.valueOf() ?? 0,
    })
  }

  return list.sort((a, b) => b.at - a.at)
})

/** The newest run with figures: its card opens on first draw. */
const newestCard = computed(() => runs.value.find((run) => run.card)?.key ?? null)

/** The run opened in detail, kept in the URL. */
const openedKey = computed(() => (typeof route.query.run === 'string' ? route.query.run : ''))

const opened = computed(() => runs.value.find((run) => run.key === openedKey.value) ?? null)

function open(run: RunView): void {
  router.replace({ query: { ...route.query, run: run.key } })
}

function closeDetail(): void {
  const query = { ...route.query }
  delete query.run
  router.replace({ query })
}

// --- loading ---------------------------------------------------------------

async function load(): Promise<void> {
  loading.value = true
  try {
    const [listed, reported] = await Promise.all([
      benchmarksApi.listJobs(props.slug).catch(() => []),
      benchmarksApi.listReportRuns(props.slug, { limit: 100 }).catch(() => null),
    ])
    jobs.value = listed
    buildOnly.value = (reported?.items ?? []).filter((run) => run.build_only)
    // Awaited here so the list draws once, with the live build in place.
    await loadLatest()
  } finally {
    loading.value = false
  }
}

async function loadLatest(): Promise<void> {
  try {
    latest.value = await benchmarksApi.buildReport(props.slug)
  } catch {
    // 409 — nothing gradable yet; anything else — no benchmark to ask.
    latest.value = null
  }
}

onMounted(load)
watch(() => props.slug, load)
</script>

<template>
  <div v-if="loading" class="space-y-3">
    <Skeleton class="h-32 w-full" />
    <Skeleton class="h-12 w-full" />
  </div>

  <!-- Not measured (not a score of zero). -->
  <div v-else-if="!runs.length" class="border border-border/50 rounded-lg p-8 text-center">
    <FlaskConical class="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
    <h3 class="text-sm font-medium text-foreground mb-1">Nothing measured yet</h3>
    <p class="text-xs text-muted-foreground max-w-md mx-auto">
      Not a score of zero — nobody has run the benchmark. Start on the
      <strong class="text-foreground">Benchmark setup</strong> tab.
    </p>
  </div>

  <!-- One run, in place of the list. -->
  <RunDetail
    v-else-if="opened"
    :slug="slug"
    :card="opened.card"
    :job-id="opened.jobId"
    :measured="opened.measured"
    @back="closeDetail"
  />

  <div v-else class="space-y-3">
    <template v-for="run in runs" :key="run.key">
      <RunCard
        v-if="run.card"
        :card="run.card"
        :measured="run.measured"
        :default-open="run.key === newestCard"
        @more="open(run)"
      />
      <section v-else class="border border-border/60 rounded-lg overflow-hidden">
        <div
          class="flex items-center gap-3 p-3 sm:p-4 cursor-pointer select-none hover:bg-muted/30"
          role="button"
          tabindex="0"
          data-testid="build-only-run"
          @click="open(run)"
          @keydown.enter.prevent="open(run)"
          @keydown.space.prevent="open(run)"
        >
          <ChevronRight class="h-4 w-4 text-muted-foreground shrink-0" />
          <div class="min-w-0 text-sm font-medium text-foreground truncate">
            Benchmark Result
            <span class="text-muted-foreground font-normal">{{ run.measured }}</span>
          </div>
          <span
            class="ml-auto shrink-0 text-xs text-muted-foreground"
            title="Questions were written and filtered; no model was asked."
          >
            {{ run.build ? `Build only · ${run.build}` : 'Build only' }}
          </span>
        </div>
      </section>
    </template>
  </div>
</template>
