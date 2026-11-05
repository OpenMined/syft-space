<script setup lang="ts">
/** Everything that happened to one kind's questions in a job, from writing through filtering. */
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkKindBuild, BenchmarkPair, BenchmarkPairStatus } from '@/api/types'
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from '@/components/ui/dialog'
import { apiErrorDetail } from '@/lib/errors'
import { droppedLines, droppedTotal } from '../../filter'
import { kindLabel } from '../../kinds'
import DraftRow from './DraftRow.vue'
import KindBuildStats from './KindBuildStats.vue'
import WriterCallBlock from './WriterCallBlock.vue'
import { loadKind, type KindOrigin } from './load'
import { FATES, fateCounts, fateLabel, narrowBlock, type Fate } from './writing'

const props = defineProps<{
  slug: string
  jobId: string
  /** The kind shown; null keeps the dialog closed. */
  generator: string | null
  build: BenchmarkKindBuild | null
}>()
const emit = defineEmits<{ close: [] }>()

const origin = ref<KindOrigin | null>(null)
const loading = ref(false)
const failed = ref(false)
const fate = ref<Fate | null>(null)
const busyId = ref<string | null>(null)
let token = 0

async function load(): Promise<void> {
  const generator = props.generator
  if (!generator) return
  const mine = ++token
  loading.value = true
  failed.value = false
  try {
    const found = await loadKind(props.slug, props.jobId, generator)
    if (mine === token) origin.value = found
  } catch (error) {
    if (mine !== token) return
    failed.value = true
    toast.error(apiErrorDetail(error, 'Could not load how these questions were made'))
  } finally {
    if (mine === token) loading.value = false
  }
}

watch(
  () => props.generator,
  (generator) => {
    origin.value = null
    fate.value = null
    if (generator) void load()
  },
  { immediate: true },
)

async function setStatus(pair: BenchmarkPair, status: BenchmarkPairStatus): Promise<void> {
  busyId.value = pair.id
  try {
    await benchmarksApi.updatePairStatus(props.slug, pair.id, status)
    toast.success(status === 'active' ? 'Marked active' : 'Rejected')
    await load()
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not change status'))
  } finally {
    busyId.value = null
  }
}

const counts = computed(() =>
  origin.value ? fateCounts(origin.value.blocks, origin.value.earlier) : {},
)
const total = computed(() => Object.values(counts.value).reduce((sum, n) => sum + (n ?? 0), 0))
const chips = computed(() => FATES.filter((f) => counts.value[f]))

const blocks = computed(() =>
  (origin.value?.blocks ?? [])
    .map((block) => narrowBlock(block, fate.value))
    .filter((block) => block !== null),
)
const earlier = computed(() =>
  (origin.value?.earlier ?? []).filter((d) => !fate.value || d.fate === fate.value),
)

/** No writer call carries the drops (no writing log, or it did not load): only the per-reason counts are known. */
const droppedFallback = computed(() => {
  const build = props.build
  if (!build || !droppedTotal(build) || !origin.value) return []
  if (origin.value.blocks.some((b) => b.dropped.length)) return []
  return droppedLines(build)
})

function pick(next: Fate | null): void {
  fate.value = fate.value === next ? null : next
}

const CHIP = 'rounded-full border px-2.5 py-0.5 text-xs transition-colors'
const CHIP_ON = 'border-foreground bg-foreground text-background'
const CHIP_OFF = 'border-border text-muted-foreground hover:text-foreground'
</script>

<template>
  <Dialog :open="generator !== null" @update:open="(open) => !open && emit('close')">
    <DialogScrollContent class="sm:max-w-5xl" data-testid="generator-dialog">
      <DialogHeader>
        <DialogTitle>{{ generator ? kindLabel(generator) : '' }}</DialogTitle>
        <DialogDescription>How this run wrote and filtered these questions.</DialogDescription>
      </DialogHeader>

      <div class="min-w-0 space-y-4">
        <KindBuildStats v-if="build" :build="build" />

        <p v-if="loading && !origin" class="text-sm text-muted-foreground">Loading…</p>
        <p v-else-if="failed && !origin" class="text-sm text-destructive">Could not load.</p>

        <template v-if="origin">
          <div v-if="total" class="flex flex-wrap gap-1.5" data-testid="fate-filter">
            <button
              type="button"
              :class="[CHIP, fate === null ? CHIP_ON : CHIP_OFF]"
              :aria-pressed="fate === null"
              @click="fate = null"
            >
              All {{ total }}
            </button>
            <button
              v-for="f in chips"
              :key="f"
              type="button"
              :class="[CHIP, fate === f ? CHIP_ON : CHIP_OFF]"
              :aria-pressed="fate === f"
              :data-testid="`fate-${f}`"
              @click="pick(f)"
            >
              {{ fateLabel(f) }} {{ counts[f] }}
            </button>
          </div>
          <p v-else class="text-sm text-muted-foreground">
            This run kept no record of these questions.
          </p>

          <p
            v-if="origin.writingFailed"
            class="text-sm text-destructive"
            data-testid="writing-failed"
          >
            Could not load the writer calls.
          </p>

          <div v-if="blocks.length" class="space-y-2">
            <WriterCallBlock
              v-for="block in blocks"
              :key="block.key"
              :block="block"
              :busy-id="busyId"
              @set-status="setStatus"
            />
          </div>

          <section v-if="droppedFallback.length" class="space-y-1" data-testid="dropped-counts">
            <h3 class="text-sm font-semibold">Dropped while writing</h3>
            <ul class="text-sm text-muted-foreground">
              <li v-for="line in droppedFallback" :key="line">{{ line }}</li>
            </ul>
          </section>

          <section v-if="earlier.length" class="space-y-2" data-testid="written-earlier">
            <h3 class="text-sm font-semibold">Written earlier</h3>
            <p
              v-if="origin.earlierFailed"
              class="text-sm text-destructive"
              data-testid="written-earlier-failed"
            >
              Could not load these questions.
            </p>
            <ul class="space-y-1.5">
              <DraftRow
                v-for="draft in earlier"
                :key="draft.id"
                :draft="draft"
                :busy="busyId === draft.id"
                @set-status="setStatus"
              />
            </ul>
          </section>
        </template>
      </div>
    </DialogScrollContent>
  </Dialog>
</template>
