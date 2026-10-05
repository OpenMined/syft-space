<template>
  <section id="report-summary" class="scroll-mt-4 space-y-4" aria-labelledby="summary-title">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 id="summary-title" class="heading-4">Summary</h2>
      <div v-if="rows.length" class="flex items-center gap-2">
        <Label for="summary-model" class="text-sm text-muted-foreground">Show summary for</Label>
        <Select :model-value="row?.model" @update:model-value="pick">
          <SelectTrigger id="summary-model" class="min-w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="r in rows" :key="r.model" :value="r.model">{{
              modelName(r.model)
            }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <template v-if="row">
      <p class="max-w-3xl text-base" data-testid="summary-sentence">
        With your data, <b class="font-semibold">{{ modelName(row.model) }}</b> answered
        <b class="font-semibold">{{ pct(row.rate_with) }}</b> of {{ count(row.asked) }} questions
        correctly. On its own, with web search, it answered
        <b class="font-semibold">{{ pct(row.rate_alone) }}</b
        >.
      </p>

      <div class="grid grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-2 lg:grid-cols-4">
        <div class="rounded-lg border border-border bg-card p-4" data-testid="tile-with">
          <div class="text-2xl font-semibold text-primary tabular-nums">
            {{ pct(row.rate_with) }}
          </div>
          <div class="mt-1 text-xs text-muted-foreground">Correct with your data</div>
        </div>
        <div class="rounded-lg border border-border bg-card p-4" data-testid="tile-alone">
          <div class="text-2xl font-semibold tabular-nums">{{ pct(row.rate_alone) }}</div>
          <div class="mt-1 text-xs text-muted-foreground">Correct on its own, with web search</div>
        </div>
        <div class="rounded-lg border border-border bg-card p-4" data-testid="tile-lift">
          <div class="text-2xl font-semibold text-primary tabular-nums">{{ points(row.lift) }}</div>
          <div class="mt-1 text-xs text-muted-foreground">Points added by your data</div>
        </div>
        <div class="rounded-lg border border-border bg-card p-4" data-testid="tile-made-up">
          <div class="text-2xl font-semibold tabular-nums">
            <span class="text-amber-700 dark:text-amber-400">{{ pct(row.made_up_alone) }}</span>
            <span> → </span>
            <span>{{ pct(row.made_up_with) }}</span>
          </div>
          <div class="mt-1 text-xs text-muted-foreground">
            Made-up answers, on its own → with your data
          </div>
        </div>
      </div>
    </template>
    <p v-else class="text-sm text-muted-foreground">No model was measured in this run.</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AcceptableValue } from 'reka-ui'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useRun } from './context'
import { count, pct, points } from './figures'
import { modelName } from './labels'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const run = useRun()

const rows = computed(() => run.data.value?.models ?? [])
const row = computed(() => run.modelReport.value ?? rows.value[0] ?? null)

function pick(value: AcceptableValue): void {
  if (typeof value === 'string') run.selectModel(value)
}
</script>
