<script setup lang="ts">
/** Where one job's time went: phases, evaluation passes, call latency. Hidden without data. */
import { computed, ref, watch } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkRunTiming } from '@/api/types'
import { armTileWords, blockBrief, shortModel } from './labels'
import { duration, hasTiming, phaseLabel, roleLabel, runSpan } from './timing'

const props = defineProps<{ slug: string; job: string; refreshKey?: number }>()

const timing = ref<BenchmarkRunTiming | null>(null)
// From the run's own timestamps, for runs recorded without timing.
const spanS = ref<number | null>(null)

async function load(): Promise<void> {
  try {
    const report = await benchmarksApi.getRunReport(props.slug, props.job)
    timing.value = hasTiming(report.timing) ? report.timing : null
    spanS.value = runSpan(report.run?.created_at, report.run?.finished_at)
  } catch {
    timing.value = null
    spanS.value = null
  }
}

const totalS = computed(() => timing.value?.total_s || spanS.value)

watch([() => props.job, () => props.refreshKey], load, { immediate: true })

const limits = computed(() => {
  const c = timing.value?.concurrency
  return c ? `Model requests at once: ${c.model}; endpoint: ${c.endpoint}.` : undefined
})

const TH = 'px-3 py-2 font-medium'
const TD = 'px-3 py-1.5 text-right tabular-nums'
</script>

<template>
  <p v-if="!timing && totalS" class="text-xs text-muted-foreground" data-testid="timing-total">
    Total <span class="tabular-nums text-foreground">{{ duration(totalS) }}</span>
  </p>
  <div v-if="timing" class="space-y-2" data-testid="timing">
    <p class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <span :title="limits" class="cursor-help" data-testid="timing-total">
        Total <span class="tabular-nums text-foreground">{{ duration(totalS) }}</span>
      </span>
      <span v-for="p in timing.phases" :key="p.phase" data-testid="timing-phase">
        {{ phaseLabel(p.phase) }}
        <span class="tabular-nums text-foreground">{{ duration(p.s) }}</span>
      </span>
    </p>

    <div class="grid gap-3 xl:grid-cols-2">
      <div
        v-if="timing.passes.length"
        class="overflow-x-auto rounded-lg border border-border bg-card"
      >
        <table class="w-full min-w-[28rem] text-sm">
          <thead class="bg-muted/40 text-xs text-muted-foreground">
            <tr class="border-b border-border">
              <th scope="col" :class="TH" class="text-left">Pass</th>
              <th scope="col" :class="TH" class="text-right">Questions</th>
              <th
                scope="col"
                :class="TH"
                class="text-right"
                title="Passes run at the same time, so they overlap."
              >
                Time
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(p, n) in timing.passes"
              :key="n"
              class="border-b border-border last:border-b-0"
              data-testid="timing-pass"
            >
              <td class="px-3 py-1.5" :title="p.model">
                {{ shortModel(p.model) }}
                <span class="text-muted-foreground">
                  · {{ armTileWords(p.arm) }} · {{ blockBrief(p.block) }}
                </span>
                <span
                  v-if="p.stopped"
                  class="ml-1 rounded bg-destructive/10 px-1.5 py-0.5 text-xs text-destructive"
                  >{{ p.stopped }}</span
                >
              </td>
              <td :class="TD">{{ p.questions }}</td>
              <td :class="TD">{{ duration(p.s) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="timing.calls.length"
        class="overflow-x-auto rounded-lg border border-border bg-card"
      >
        <table class="w-full min-w-[28rem] text-sm">
          <thead class="bg-muted/40 text-xs text-muted-foreground">
            <tr class="border-b border-border">
              <th scope="col" :class="TH" class="text-left">Model</th>
              <th scope="col" :class="TH" class="text-right">Calls</th>
              <th scope="col" :class="TH" class="text-right">Mean</th>
              <th scope="col" :class="TH" class="text-right">p90</th>
              <th scope="col" :class="TH" class="text-right">Max</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in timing.calls"
              :key="`${c.role}:${c.model}`"
              class="border-b border-border last:border-b-0"
              data-testid="timing-call"
            >
              <td class="px-3 py-1.5" :title="c.model">
                {{ shortModel(c.model) }}
                <span class="text-muted-foreground">· {{ roleLabel(c.role) }}</span>
              </td>
              <td :class="TD">
                {{ c.count }}
                <span v-if="c.failed" class="text-destructive">({{ c.failed }} failed)</span>
              </td>
              <td :class="TD">{{ duration(c.mean_s) }}</td>
              <td :class="TD">{{ duration(c.p90_s) }}</td>
              <td :class="TD">{{ duration(c.max_s) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
