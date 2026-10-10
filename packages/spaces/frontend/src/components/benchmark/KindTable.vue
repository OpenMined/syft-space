<script setup lang="ts">
/** How each kind's generation went in one job; hidden when the job kept no stats. */
import { computed, ref, watch } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkKindBuild } from '@/api/types'
import { droppedLines, droppedTotal, maskedCounts, readText, stoppedLabel } from './filter'
import { kindLabel } from './report/labels'
import { compareKinds } from './questionOrder'

const props = defineProps<{ slug: string; job: string; refreshKey?: number }>()

const kinds = ref<BenchmarkKindBuild[]>([])

async function load(): Promise<void> {
  try {
    const page = await benchmarksApi.getRunGenerated(props.slug, props.job, { limit: 1 })
    kinds.value = [...(page.kinds ?? [])].sort((a, b) => compareKinds(a.kind, b.kind))
  } catch {
    kinds.value = []
  }
}

watch([() => props.job, () => props.refreshKey], load, { immediate: true })

const masking = computed(() => kinds.value.some((k) => maskedCounts(k)))

const STOP_TONE: Record<string, string> = {
  'budget reached': 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  'ran out of material': 'bg-muted text-muted-foreground',
  'failure streak': 'bg-destructive/10 text-destructive',
  cancelled: 'bg-muted text-muted-foreground',
}
</script>

<template>
  <div
    v-if="kinds.length"
    class="overflow-x-auto rounded-lg border border-border bg-card"
    data-testid="kind-table"
  >
    <table class="w-full min-w-[36rem] text-sm">
      <thead class="bg-muted/40 text-xs text-muted-foreground">
        <tr class="border-b border-border">
          <th scope="col" class="px-3 py-2 text-left font-medium">Kind</th>
          <th
            scope="col"
            class="px-3 py-2 text-right font-medium"
            title="Questions written, of the budget."
          >
            Written
          </th>
          <th
            scope="col"
            class="px-3 py-2 text-right font-medium"
            title="Passages or articles read, of those available."
          >
            Read
          </th>
          <th
            scope="col"
            class="px-3 py-2 text-right font-medium"
            title="Questions thrown away while writing; hover a number for reasons."
          >
            Dropped
          </th>
          <th
            v-if="masking"
            scope="col"
            class="px-3 py-2 text-right font-medium"
            title="Masking questions cut by spaCy / written by the LLM; hover a number for why."
          >
            spaCy / LLM
          </th>
          <th scope="col" class="px-3 py-2 text-left font-medium">Stopped</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="k in kinds"
          :key="k.kind"
          class="border-b border-border last:border-b-0"
          data-testid="kind-build-row"
        >
          <th scope="row" class="px-3 py-2 text-left font-medium">{{ kindLabel(k.kind) }}</th>
          <td class="px-3 py-2 text-right tabular-nums">{{ k.written }} / {{ k.budget }}</td>
          <td class="px-3 py-2 text-right tabular-nums text-muted-foreground">
            {{ readText(k) }}
          </td>
          <td class="px-3 py-2 text-right tabular-nums">
            <span
              v-if="droppedTotal(k)"
              class="cursor-help underline decoration-dotted underline-offset-2"
              :title="droppedLines(k).join('\n')"
              data-testid="kind-dropped"
              >{{ droppedTotal(k) }}</span
            >
            <span v-else class="text-muted-foreground">0</span>
          </td>
          <td v-if="masking" class="px-3 py-2 text-right tabular-nums" data-testid="kind-masked">
            <span
              v-if="maskedCounts(k)?.tip"
              class="cursor-help underline decoration-dotted underline-offset-2"
              :title="maskedCounts(k)!.tip"
              >{{ maskedCounts(k)!.text }}</span
            >
            <span v-else-if="maskedCounts(k)">{{ maskedCounts(k)!.text }}</span>
            <span v-else class="text-muted-foreground">—</span>
          </td>
          <td class="px-3 py-2">
            <span
              class="rounded px-1.5 py-0.5 text-xs"
              :class="STOP_TONE[k.stopped] ?? 'bg-muted text-muted-foreground'"
            >
              {{ stoppedLabel(k.stopped) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
