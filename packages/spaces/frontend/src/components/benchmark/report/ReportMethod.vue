<template>
  <section v-if="steps" class="space-y-3" data-testid="report-method">
    <h2 class="heading-4">How this was tested</h2>
    <div class="grid grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-3">
      <div class="rounded-lg border bg-card p-4" data-testid="funnel-written">
        <p class="text-2xl font-semibold tabular-nums">{{ count(steps.written) }}</p>
        <p class="mt-2 text-sm text-muted-foreground">
          Questions written from your last 24 hours of articles
        </p>
      </div>
      <div class="rounded-lg border bg-card p-4" data-testid="funnel-removed">
        <p class="text-2xl font-semibold tabular-nums text-warning">
          {{ count(steps.removed_total) }}
        </p>
        <div class="mt-2 flex items-start gap-1.5">
          <p class="text-sm text-muted-foreground">Removed by quality checks</p>
          <span v-if="removedTip" class="mt-0.5 flex"><InfoTip :text="removedTip" /></span>
        </div>
      </div>
      <div class="rounded-lg border border-primary bg-primary/5 p-4" data-testid="funnel-asked">
        <p class="text-2xl font-semibold tabular-nums text-primary">
          {{ count(steps.asked || null) }}
        </p>
        <p class="mt-2 text-sm text-muted-foreground">
          Kept and asked to every model, then retired
        </p>
      </div>
    </div>
    <dl class="divide-y rounded-lg border bg-card text-sm">
      <div
        v-for="row in settings"
        :key="row.key"
        class="grid grid-cols-1 gap-1 px-4 py-3 break-words sm:grid-cols-[14rem_minmax(0,1fr)] sm:gap-4"
        :data-testid="`setting-${row.key}`"
      >
        <dt class="font-medium">{{ row.label }}</dt>
        <dd class="text-muted-foreground">{{ row.value ?? '—' }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import InfoTip from '../InfoTip.vue'
import { useRun } from './context'
import { removedReasonLabel } from './labels'
import { methodSettings } from './selectors'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const run = useRun()

const steps = computed(() => run.data.value?.funnel ?? null)
const settings = computed(() => (run.data.value ? methodSettings(run.data.value) : []))

const removedTip = computed(() => {
  const removed = Object.entries(steps.value?.removed ?? {}).filter(([, n]) => n > 0)
  if (!removed.length) return null
  return `${removed.map(([reason, n]) => `${removedReasonLabel(reason)}: ${n}`).join(', ')}.`
})

function count(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toLocaleString('en') : '—'
}
</script>
