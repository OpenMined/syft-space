<script setup lang="ts">
/**
 * The question/answer pairs of one status band, grouped by the generator
 * that built them — shared by the Generation and Filtering blocks, which
 * show the same rows pre-filtered differently by the parent.
 *
 * Fetched in full rather than paged: a run realistically produces low
 * hundreds of pairs, and grouping by generator needs every row in hand to
 * count them, not one page at a time. `MAX_FETCH` is a safety stop, not a
 * design limit — past it the list says so instead of quietly truncating.
 */
import { computed, reactive, ref, watch } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { sortQuestions } from './questionOrder'
import { apiErrorDetail } from '@/lib/errors'
import { generatorWords } from './labels'
import PairRow from './PairRow.vue'
import type { BenchmarkPair, BenchmarkPairStatus } from '@/api/types'

const props = defineProps<{
  slug: string
  status?: BenchmarkPairStatus
  refreshKey: number
  /** One launch's questions; empty — everything this endpoint has. */
  job?: string
}>()

const PAGE = 100
const MAX_FETCH = 1000
const items = ref<BenchmarkPair[]>([])
const total = ref(0)
const loading = ref(false)
const busyId = ref<string | null>(null)
const truncated = ref(false)
const openGroups = reactive<Record<string, boolean>>({})

async function load(): Promise<void> {
  loading.value = true
  try {
    const first = await benchmarksApi.listPairs(props.slug, {
      status: props.status,
      job: props.job,
      limit: PAGE,
      offset: 0,
    })
    const all = first.items.slice()
    let offset = PAGE
    while (offset < first.total && offset < MAX_FETCH) {
      const page = await benchmarksApi.listPairs(props.slug, {
        status: props.status,
        job: props.job,
        limit: PAGE,
        offset,
      })
      all.push(...page.items)
      offset += PAGE
    }
    items.value = all
    total.value = first.total
    truncated.value = first.total > all.length
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not load pairs'))
  } finally {
    loading.value = false
  }
}

watch([() => props.status, () => props.refreshKey, () => props.job], load, {
  immediate: true,
})

async function setStatus(pair: BenchmarkPair, status: BenchmarkPairStatus): Promise<void> {
  busyId.value = pair.id
  try {
    const updated = await benchmarksApi.updatePairStatus(props.slug, pair.id, status)
    items.value = items.value.map((row) => (row.id === updated.id ? updated : row))
    toast.success(`Marked ${status}`)
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not change status'))
  } finally {
    busyId.value = null
  }
}

async function remove(pair: BenchmarkPair): Promise<void> {
  if (!window.confirm('Delete this pair for good? This cannot be undone.')) return
  busyId.value = pair.id
  try {
    await benchmarksApi.deletePair(props.slug, pair.id)
    items.value = items.value.filter((row) => row.id !== pair.id)
    total.value -= 1
    toast.success('Deleted')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not delete this pair'))
  } finally {
    busyId.value = null
  }
}

const groups = computed(() => {
  const byGenerator = new Map<string, BenchmarkPair[]>()
  const ordered = sortQuestions(items.value, (pair) => ({
    generator: pair.generator,
    createdAt: pair.created_at,
    id: pair.id,
  }))
  for (const pair of ordered) {
    const list = byGenerator.get(pair.generator)
    if (list) list.push(pair)
    else byGenerator.set(pair.generator, [pair])
  }
  return [...byGenerator.keys()].map((generator) => ({
    generator,
    pairs: byGenerator.get(generator)!,
  }))
})

function toggle(generator: string): void {
  openGroups[generator] = !openGroups[generator]
}
</script>

<template>
  <div class="space-y-2">
    <p class="text-xs text-muted-foreground">
      {{ total }} pair(s)
      <span v-if="truncated">— showing the first {{ items.length }}</span>
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
            {{ generatorWords(group.generator).label }}
          </span>
          <span class="text-xs text-muted-foreground">{{ group.pairs.length }}</span>
        </button>
        <ul v-if="openGroups[group.generator]" class="border-t border-border/60 p-2 space-y-2">
          <PairRow
            v-for="pair in group.pairs"
            :key="pair.id"
            :pair="pair"
            :busy="busyId === pair.id"
            @set-status="(status) => setStatus(pair, status)"
            @remove="remove(pair)"
          />
        </ul>
      </div>
    </div>
  </div>
</template>
