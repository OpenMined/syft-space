<template>
  <section class="space-y-3" aria-labelledby="models-title">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 id="models-title" class="heading-4">Every model, with and without your data</h2>
        <p class="text-sm text-muted-foreground">
          Share of {{ count(asked) }} questions answered correctly. Select a model for its full
          results.
        </p>
      </div>
      <div class="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-hidden="true">
        <span class="inline-flex items-center gap-1.5">
          <span class="size-2.5 rounded-sm bg-muted-foreground" />On its own, with web search
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="size-2.5 rounded-sm bg-primary" />With your data
        </span>
      </div>
    </div>

    <div class="relative overflow-x-auto rounded-lg border border-border bg-card">
      <table class="w-full text-sm sm:min-w-[640px]">
        <thead class="bg-muted/40 text-xs text-muted-foreground">
          <tr class="border-b border-border">
            <th scope="col" class="px-4 py-2.5 text-left font-medium">Model</th>
            <th scope="col" class="px-4 py-2.5 text-left font-medium">Correct</th>
            <th scope="col" class="hidden px-3 py-2.5 text-right font-medium sm:table-cell">
              Lift
            </th>
            <th scope="col" class="hidden px-3 py-2.5 text-right font-medium sm:table-cell">
              Made up
            </th>
            <th scope="col" class="w-10"><span class="sr-only">Select</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in rows"
            :key="r.model"
            class="cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-muted/40"
            :class="{ 'bg-primary/5': r.model === run.model.value }"
            data-testid="model-row"
            @click="choose(r.model)"
          >
            <td class="px-4 py-3">
              <button
                type="button"
                class="text-left font-medium hover:underline focus-visible:underline focus-visible:outline-none"
                :aria-current="r.model === run.model.value ? 'true' : undefined"
                @click.stop="choose(r.model)"
              >
                {{ modelName(r.model) }}
              </button>
              <div v-if="vendorName(r.model)" class="text-xs text-muted-foreground">
                {{ vendorName(r.model) }}
              </div>
            </td>
            <td class="w-1/2 px-4 py-3">
              <div class="space-y-1.5">
                <div class="flex items-center gap-3">
                  <div
                    class="h-2 flex-1 overflow-hidden rounded-full bg-muted"
                    role="img"
                    :aria-label="`On its own, with web search: ${pct(r.rate_alone)}`"
                  >
                    <div
                      class="h-full rounded-full bg-muted-foreground"
                      :style="{ width: width(r.rate_alone) }"
                    />
                  </div>
                  <span class="w-10 text-right text-muted-foreground tabular-nums">
                    {{ pct(r.rate_alone) }}
                  </span>
                </div>
                <div class="flex items-center gap-3">
                  <div
                    class="h-2 flex-1 overflow-hidden rounded-full bg-muted"
                    role="img"
                    :aria-label="`With your data: ${pct(r.rate_with)}`"
                  >
                    <div
                      class="h-full rounded-full bg-primary"
                      :style="{ width: width(r.rate_with) }"
                    />
                  </div>
                  <span class="w-10 text-right font-medium tabular-nums">{{
                    pct(r.rate_with)
                  }}</span>
                </div>
                <!-- Narrow screens: Lift and Made up columns fold in here. -->
                <div class="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs sm:hidden">
                  <span>
                    <span class="text-muted-foreground">Lift</span>
                    <b class="ml-1 font-semibold text-primary tabular-nums">{{ points(r.lift) }}</b>
                  </span>
                  <span class="text-muted-foreground">
                    Made up
                    <span class="ml-1 whitespace-nowrap tabular-nums">{{
                      madeUp(r.made_up_alone, r.made_up_with)
                    }}</span>
                  </span>
                </div>
              </div>
            </td>
            <td
              class="hidden px-3 py-3 text-right text-base font-semibold text-primary tabular-nums sm:table-cell"
            >
              {{ points(r.lift) }}
            </td>
            <td
              class="hidden px-3 py-3 text-right whitespace-nowrap text-muted-foreground tabular-nums sm:table-cell"
            >
              {{ madeUp(r.made_up_alone, r.made_up_with) }}
            </td>
            <td class="pr-3 text-muted-foreground">
              <ChevronRight class="size-4" aria-hidden="true" />
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="5" class="px-4 py-6 text-muted-foreground">
              No model was measured in this run.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { useRun } from './context'
import { count, DASH, pct, points } from './figures'
import { modelName, vendorName } from './labels'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const run = useRun()

const rows = computed(() => run.data.value?.models ?? [])
const asked = computed(() => (run.modelReport.value ?? rows.value[0])?.asked ?? null)

function width(x: number | null): string {
  return `${Math.min(Math.max(x ?? 0, 0), 1) * 100}%`
}

function madeUp(alone: number | null, withData: number | null): string {
  if (alone === null && withData === null) return DASH
  return `${pct(alone)} → ${pct(withData)}`
}

function choose(model: string): void {
  run.selectModel(model)
  document.getElementById('report-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
