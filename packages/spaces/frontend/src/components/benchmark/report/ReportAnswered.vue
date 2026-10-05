<template>
  <section
    class="space-y-5 rounded-lg border border-border bg-card p-4 sm:p-5"
    aria-labelledby="answered-title"
  >
    <div>
      <h2 id="answered-title" class="heading-4">How {{ name }} answered</h2>
      <p class="text-sm text-muted-foreground">
        Every answer is graded as right, didn’t know, or made up.
      </p>
    </div>

    <template v-if="summary && summary.asked">
      <div
        v-for="arm in arms"
        :key="arm.key"
        class="space-y-2"
        :data-testid="`answered-${arm.key}`"
      >
        <h3 class="text-sm font-medium">{{ arm.label }}</h3>
        <div
          class="flex h-4 gap-0.5 overflow-hidden rounded"
          role="img"
          :aria-label="arm.parts.map((p) => `${p.label} ${pct(p.share)}`).join(', ')"
        >
          <div
            v-for="p in arm.parts"
            v-show="p.share"
            :key="p.key"
            :class="p.bar"
            :style="{ width: `${(p.share ?? 0) * 100}%` }"
          />
        </div>
        <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span v-for="p in arm.parts" :key="p.key" class="inline-flex items-center gap-1.5">
            <span class="size-2 rounded-sm" :class="p.bar" aria-hidden="true" />
            {{ p.label }}
            <b class="font-semibold" :class="p.text">{{ pct(p.share) }}</b>
          </span>
        </div>
      </div>
      <p v-if="leftOut" class="text-xs text-muted-foreground" data-testid="answered-left-out">
        {{ leftOut }}
      </p>
    </template>
    <p v-else class="text-sm text-muted-foreground">No graded answers for this model.</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BenchmarkTally } from '@/api/types'
import { useRun } from './context'
import { pct, rate } from './figures'
import { ARM_LABEL, modelName, verdictLabel } from './labels'
import { ARM_KEY, type Arm } from './types'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const run = useRun()

const summary = computed(() => run.modelReport.value)
const name = computed(() => (run.model.value ? modelName(run.model.value) : 'the model'))

const PARTS = [
  { key: 'correct', bar: 'bg-primary', text: 'text-foreground' },
  { key: 'abstain', bar: 'bg-muted-foreground/35', text: 'text-foreground' },
  { key: 'hallucinate', bar: 'bg-warning', text: 'text-amber-700 dark:text-amber-400' },
] as const

function parts(t: BenchmarkTally) {
  return PARTS.map((p) => ({ ...p, label: verdictLabel(p.key), share: rate(t[p.key], t.graded) }))
}

const arms = computed(() => {
  const s = summary.value
  if (!s) return []
  return (['closed', 'ctx'] as Arm[]).map((key) => ({
    key,
    label: ARM_LABEL[key],
    parts: parts(s.tally[ARM_KEY[key]]),
  }))
})

const leftOut = computed(() => {
  const s = summary.value
  if (!s) return null
  const { alone, with: withData } = s.tally
  const pending = alone.pending + withData.pending
  const technical = alone.technical + withData.technical
  const bits: string[] = []
  if (pending) bits.push(`${pending} not graded yet`)
  if (technical) bits.push(`${technical} not measured`)
  if (!bits.length) return null
  const n = pending + technical
  return `${n} ${n === 1 ? 'answer is' : 'answers are'} left out of these shares: ${bits.join(', ')}.`
})
</script>
