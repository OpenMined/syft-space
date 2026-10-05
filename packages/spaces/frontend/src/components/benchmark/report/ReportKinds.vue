<template>
  <section
    class="space-y-4 rounded-lg border border-border bg-card p-4 sm:p-5"
    aria-labelledby="kinds-title"
  >
    <div>
      <h2 id="kinds-title" class="heading-4">Where your data helped most</h2>
      <p class="text-sm text-muted-foreground">
        {{ name }}, by kind of question. Select one to filter the questions below.
      </p>
    </div>

    <div v-if="kinds.length" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-xs text-muted-foreground">
          <tr class="border-b border-border">
            <th scope="col" class="py-2 pr-3 text-left font-medium">Kind of question</th>
            <th scope="col" class="px-3 py-2 text-right font-medium">On its own → with</th>
            <th scope="col" class="py-2 pl-3 text-right font-medium">Lift</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="k in kinds"
            :key="k.generator"
            class="cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-muted/40"
            :class="{ 'bg-primary/10': k.generator === active }"
            data-testid="kind-row"
            @click="toggle(k.generator)"
          >
            <td class="py-2.5 pr-3">
              <button
                type="button"
                class="text-left hover:underline focus-visible:underline focus-visible:outline-none"
                :class="{ 'font-medium text-primary': k.generator === active }"
                :aria-pressed="k.generator === active"
                @click.stop="toggle(k.generator)"
              >
                {{ kindLabel(k.generator) }}
              </button>
            </td>
            <td class="px-3 py-2.5 text-right whitespace-nowrap text-muted-foreground tabular-nums">
              {{ pct(k.rate_alone) }} → {{ pct(k.rate_with) }}
            </td>
            <td class="py-2.5 pl-3 text-right font-semibold text-primary tabular-nums">
              {{ points(k.lift) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="text-sm text-muted-foreground">No graded answers for this model.</p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick } from 'vue'
import { useRun } from './context'
import { pct, points } from './figures'
import { kindLabel, modelName } from './labels'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const run = useRun()

const kinds = computed(() => run.modelReport.value?.kinds ?? [])
const name = computed(() => (run.model.value ? modelName(run.model.value) : 'The model'))
const active = computed(() => run.kind.value)

function toggle(generator: string): void {
  const next = active.value === generator ? null : generator
  run.setKind(next)
  if (next) {
    void nextTick(() =>
      document
        .getElementById('report-questions')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    )
  }
}
</script>
