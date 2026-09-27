<script setup lang="ts">
/**
 * Answers for one endpoint — shared by the Execution block (what it just
 * produced, mostly still pending) and the Judging block (the same rows,
 * once graded, with the override buttons for a second look).
 *
 * Grouped by methodology first (arm and check — the report never mixes
 * their figures either, see armWords/blockWords), generator within that,
 * same reasoning and shape as PairList's own generator grouping.
 *
 * Fetched in full rather than paged: grouping needs every row in hand to
 * count them, not one page at a time. `MAX_FETCH` is a safety stop, not a
 * design limit — past it the list says so instead of quietly truncating.
 */
import { computed, reactive, ref, watch } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { apiErrorDetail } from '@/lib/errors'
import { ARMS, BLOCKS, armWords, blockWords, generatorWords } from './labels'
import ResultRow from './ResultRow.vue'
import type { BenchmarkResult, BenchmarkVerdict } from '@/api/types'

const props = defineProps<{
  slug: string
  refreshKey: number
  /** The known generators, in the benchmark's own order — sets group order. */
  generators?: string[]
}>()

const PAGE = 100
const MAX_FETCH = 1000
const items = ref<BenchmarkResult[]>([])
const total = ref(0)
const loading = ref(false)
const busyId = ref<string | null>(null)
const truncated = ref(false)
const openGroups = reactive<Record<string, boolean>>({})

async function load(): Promise<void> {
  loading.value = true
  try {
    const first = await benchmarksApi.listResults(props.slug, { limit: PAGE, offset: 0 })
    const all = first.items.slice()
    let offset = PAGE
    while (offset < first.total && offset < MAX_FETCH) {
      const page = await benchmarksApi.listResults(props.slug, { limit: PAGE, offset })
      all.push(...page.items)
      offset += PAGE
    }
    items.value = all
    total.value = first.total
    truncated.value = first.total > all.length
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not load results'))
  } finally {
    loading.value = false
  }
}

watch(() => props.refreshKey, load, { immediate: true })

async function override(row: BenchmarkResult, verdict: BenchmarkVerdict): Promise<void> {
  const reasoning = window.prompt('Why? (shown next to the verdict)', '') ?? ''
  busyId.value = row.id
  try {
    const updated = await benchmarksApi.overrideVerdict(props.slug, row.id, verdict, reasoning)
    items.value = items.value.map((existing) => (existing.id === updated.id ? updated : existing))
    toast.success('Verdict overridden')
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not override this verdict'))
  } finally {
    busyId.value = null
  }
}

const ARM_ORDER = Object.keys(ARMS)
const BLOCK_ORDER = Object.keys(BLOCKS)

function generatorGroups(rows: BenchmarkResult[]) {
  const byGenerator = new Map<string, BenchmarkResult[]>()
  for (const row of rows) {
    const list = byGenerator.get(row.generator)
    if (list) list.push(row)
    else byGenerator.set(row.generator, [row])
  }
  const order = props.generators ?? []
  const known = order.filter((key) => byGenerator.has(key))
  const unknown = [...byGenerator.keys()].filter((key) => !order.includes(key)).sort()
  return [...known, ...unknown].map((generator) => ({
    generator,
    rows: byGenerator.get(generator)!,
  }))
}

const groups = computed(() => {
  const byMethodology = new Map<string, BenchmarkResult[]>()
  for (const row of items.value) {
    const key = `${row.context_mode}|${row.block}`
    const list = byMethodology.get(key)
    if (list) list.push(row)
    else byMethodology.set(key, [row])
  }
  function splitKey(key: string): [string, string] {
    const [arm = '', block = ''] = key.split('|')
    return [arm, block]
  }

  return [...byMethodology.entries()]
    .sort(([a], [b]) => {
      const [armA, blockA] = splitKey(a)
      const [armB, blockB] = splitKey(b)
      const armDiff = ARM_ORDER.indexOf(armA) - ARM_ORDER.indexOf(armB)
      return armDiff !== 0 ? armDiff : BLOCK_ORDER.indexOf(blockA) - BLOCK_ORDER.indexOf(blockB)
    })
    .map(([key, rows]) => {
      const [contextMode, block] = splitKey(key)
      return {
        key,
        label: `${armWords(contextMode)} · ${blockWords(block)}`,
        count: rows.length,
        generators: generatorGroups(rows),
      }
    })
})

function toggle(groupKey: string): void {
  openGroups[groupKey] = !openGroups[groupKey]
}

function generatorLabel(key: string): string {
  return generatorWords(key).label || 'Unknown generator'
}
</script>

<template>
  <div class="space-y-3">
    <p class="text-xs text-muted-foreground">
      {{ total }} result(s)
      <span v-if="truncated">— showing the first {{ items.length }}</span>
    </p>
    <p v-if="loading && items.length === 0" class="text-sm text-muted-foreground">Loading…</p>
    <p v-else-if="items.length === 0" class="text-sm text-muted-foreground">Nothing here yet.</p>
    <div v-else class="space-y-4">
      <div v-for="methodology in groups" :key="methodology.key" class="space-y-1.5">
        <p class="text-xs font-medium text-foreground">
          {{ methodology.label }} <span class="text-muted-foreground">{{ methodology.count }}</span>
        </p>
        <div class="space-y-1.5">
          <div
            v-for="group in methodology.generators"
            :key="group.generator"
            class="rounded-md border border-border/60"
          >
            <button
              type="button"
              class="w-full flex items-center gap-1.5 p-2 text-left cursor-pointer"
              @click="toggle(`${methodology.key}::${group.generator}`)"
            >
              <ChevronRight
                class="h-3.5 w-3.5 shrink-0 transition-transform"
                :class="{ 'rotate-90': openGroups[`${methodology.key}::${group.generator}`] }"
              />
              <span class="text-sm font-medium text-foreground">
                {{ generatorLabel(group.generator) }}
              </span>
              <span class="text-xs text-muted-foreground">{{ group.rows.length }}</span>
            </button>
            <ul
              v-if="openGroups[`${methodology.key}::${group.generator}`]"
              class="border-t border-border/60 p-2 space-y-2"
            >
              <ResultRow
                v-for="row in group.rows"
                :key="row.id"
                :result="row"
                :busy="busyId === row.id"
                @override="(verdict) => override(row, verdict)"
              />
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
