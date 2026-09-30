<script setup lang="ts">
/**
 * Every run this endpoint has behind it, newest first.
 *
 * The page answers one question the marketplace page never asks: **which of
 * these runs speaks for my endpoint, and do I want it to?** So a run is a card
 * with the same figures in the same places, the newest one open and the rest
 * shut, and each carries the single button that publishes it or takes it down.
 *
 * Publishing an earlier run over a later one is deliberate, not a repair: a
 * newer run can rest on a question set that turned out to be wrong, or on a
 * night when a model under test was answering badly for reasons of its own.
 * Nothing is deleted either way — the runs measured after the chosen one are
 * marked withdrawn, and choosing the newer one again puts it back.
 *
 * Running a measurement is the other tab's job. Nothing here starts one.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { FlaskConical } from 'lucide-vue-next'

import RunCard from '@/components/benchmark/RunCard.vue'
import RunDetail from '@/components/benchmark/RunDetail.vue'
import type { RunMarketplace } from '@/components/benchmark/runs'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { marketplacesApi } from '@/api/endpoints/marketplaces'
import { settingsApi } from '@/api/endpoints/settings'
import { apiErrorDetail } from '@/lib/errors'
import type {
  BenchmarkCard,
  BenchmarkReport,
  BenchmarksMode,
  EndpointQualityResponse,
  MarketplaceListItem,
  QualityCardSummary,
} from '@/api/types'

const props = defineProps<{ slug: string }>()

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const quality = ref<EndpointQualityResponse | null>(null)
const history = ref<QualityCardSummary[]>([])
const marketplaces = ref<MarketplaceListItem[]>([])
/**
 * The generators the benchmark knows, in its own order.
 *
 * Only the run's own page needs them, to group its questions the way the
 * console does. Asked for with everything else rather than when a run is
 * opened: it is one small request, and a tab that fills in a beat after it is
 * opened reads as a glitch.
 */
const generators = ref<string[]>([])
const mode = ref<BenchmarksMode>('off')

/**
 * The card as it would be built from what is graded right now.
 *
 * Stored by nobody: the benchmark recomputes it from its own database on every
 * ask. It is a run like any other — it simply has not been reported to this
 * Space yet, and its own Public button is what reports it.
 */
const latest = ref<BenchmarkReport | null>(null)

/**
 * A stamp the way the Space stores it, read as what it is.
 *
 * The cards table keeps naive datetimes, and they are UTC. Handed to `Date`
 * without a zone a browser reads them as local time, which moves every run by
 * the reader's own offset — enough to reorder two runs of the same evening.
 */
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
  /** Null for the run that has not been reported to this Space yet. */
  cardId: string | null
  card: BenchmarkCard | BenchmarkReport
  measured: string
  at: number
  published: boolean
}

/**
 * Where the published card can be seen, as links into the marketplaces.
 *
 * The hub addresses an endpoint the way GitHub addresses a repository —
 * `/{username}/{slug}` — so the Space can build the link itself from what it
 * already knows about each marketplace it publishes to.
 */
const publishedAt = computed<RunMarketplace[]>(() => {
  const ids = new Set(quality.value?.published_to ?? [])
  return marketplaces.value
    .filter((row) => ids.has(row.id))
    .map((row) => ({
      id: row.id,
      name: row.name,
      url: `${row.url.replace(/\/$/, '')}/${row.username}/${props.slug}`,
    }))
})

const runs = computed<RunView[]>(() => {
  const stored: RunView[] = history.value.map((card) => ({
    key: card.id,
    cardId: card.id,
    card: card.report,
    measured: formatMoment(card.checked_at),
    at: moment(card.checked_at)?.valueOf() ?? 0,
    published: card.standing,
  }))

  const build = latest.value
  if (build) {
    const at = moment(build.checked_at)?.valueOf() ?? 0
    // The same measurement, once it has been reported: the stored card and this
    // build are one run, and showing it twice would invite publishing it twice.
    const alreadyStored = stored.some((run) => Math.abs(run.at - at) < 1000)
    if (!alreadyStored) {
      stored.push({
        key: 'latest',
        cardId: null,
        card: build,
        measured: formatMoment(build.checked_at),
        at,
        published: false,
      })
    }
  }

  return stored.sort((a, b) => b.at - a.at)
})

/**
 * The run opened on its own, if any — in the address rather than in memory.
 *
 * The tab already lives there for the same reason: a reload, or a link sent to
 * somebody else, should land where the sender was rather than at the top of
 * the list.
 */
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
    const [card, benchmarks, past, places, target] = await Promise.all([
      endpointsApi.getQuality(props.slug),
      settingsApi.getBenchmarksMode().catch(() => ({ mode: 'off' as BenchmarksMode })),
      endpointsApi.getQualityHistory(props.slug).catch(() => ({ cards: [] })),
      marketplacesApi.list().catch(() => []),
      benchmarksApi.getTarget(props.slug).catch(() => null),
    ])
    quality.value = card
    mode.value = benchmarks.mode
    history.value = past.cards
    marketplaces.value = places
    generators.value = target?.capabilities?.generators ?? []
    // Inside the load, not after it: drawn before this arrives, the list is
    // one run short, the stored card stands at the top and opens as the newest
    // — and when the unreported run then takes that place, the card below it
    // is a component that already exists and stays open. Two runs open at
    // once, and the lower one open again after every reload.
    await loadLatest()
  } catch {
    quality.value = null
    history.value = []
  } finally {
    loading.value = false
  }
}

async function loadLatest(): Promise<void> {
  try {
    latest.value = await benchmarksApi.buildReport(props.slug)
  } catch {
    // 409 — nothing gradable yet, the ordinary state of an endpoint nobody has
    // measured; anything else — no benchmark to ask. Either way there is no
    // unreported run, and neither is worth a toast on a page opened to read
    // what is already there.
    latest.value = null
  }
}

// --- what stands in the owner's name ---------------------------------------

const working = ref<string | null>(null)

async function publish(run: RunView): Promise<void> {
  working.value = run.key
  try {
    if (run.cardId === null) {
      // Not reported yet: the benchmark builds it again and hands it over, and
      // the Space publishes it as it does any fresh card.
      await benchmarksApi.publishReport(props.slug)
      toast.success('Published')
    } else {
      const result = await endpointsApi.publishQualityCard(props.slug, run.cardId)
      const refused = result.results.filter((row) => !row.success && row.supported)
      if (refused.length) {
        // Said plainly rather than swallowed: what stands here has changed, but
        // the marketplaces are still showing the other run.
        toast.warning(`Published here; ${refused.length} marketplace(s) refused`)
      } else {
        toast.success('Published')
      }
    }
    await load()
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not publish that run'))
  } finally {
    working.value = null
  }
}

async function retract(run: RunView): Promise<void> {
  working.value = run.key
  try {
    const result = await endpointsApi.retractQuality(props.slug)
    const refused = result.results.filter((row) => !row.success && row.supported)
    if (!result.cleared) {
      toast.info('Nothing was published')
    } else if (refused.length) {
      toast.warning(`Withdrawn here; ${refused.length} marketplace(s) refused`)
    } else {
      toast.success('Withdrawn')
    }
    await load()
  } catch {
    toast.error('Could not withdraw the card')
  } finally {
    working.value = null
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

  <!-- Nobody measured this endpoint. Not a score of zero — the absence of a
       claim, and it has to read that way. -->
  <div v-else-if="!runs.length" class="border border-border/50 rounded-lg p-8 text-center">
    <FlaskConical class="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
    <h3 class="text-sm font-medium text-foreground mb-1">Nothing measured yet</h3>
    <p class="text-xs text-muted-foreground max-w-md mx-auto">
      Not a score of zero — nobody has run the benchmark. Start on the
      <strong class="text-foreground">Benchmark</strong> tab.
      <span v-if="mode === 'off'">Reporting is off in Settings.</span>
    </p>
  </div>

  <!-- One run, in place of the list rather than beside it. -->
  <RunDetail
    v-else-if="opened"
    :slug="slug"
    :generators="generators"
    :card="opened.card"
    :measured="opened.measured"
    :published="opened.published"
    :marketplaces="publishedAt"
    :busy="working !== null"
    :working="working === opened.key"
    @back="closeDetail"
    @publish="publish(opened)"
    @retract="retract(opened)"
  />

  <div v-else class="space-y-3">
    <RunCard
      v-for="(run, index) in runs"
      :key="run.key"
      :card="run.card"
      :measured="run.measured"
      :published="run.published"
      :marketplaces="publishedAt"
      :default-open="index === 0"
      :busy="working !== null"
      :working="working === run.key"
      @publish="publish(run)"
      @retract="retract(run)"
      @more="open(run)"
    />
  </div>
</template>
