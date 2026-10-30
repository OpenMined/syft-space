<template>
  <div role="status" class="flex flex-col gap-2">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-col gap-0.5">
        <Hint :text="planTip">
          <b class="font-semibold" data-testid="run-step">{{ progressTitle(job) }}</b>
        </Hint>
        <span class="text-sm text-muted-foreground">
          {{ phaseText(job.phase) }}
          You can leave this page and the results will appear under
          <RouterLink :to="runsListLocation()" class="font-medium text-primary hover:underline">
            Benchmark results</RouterLink
          >.
        </span>
      </div>
      <Button variant="outline" :disabled="cancelling" @click="emit('stop')">
        {{ cancelling ? 'Stopping…' : 'Stop run' }}
      </Button>
    </div>
    <div class="h-1.5 overflow-hidden rounded-full bg-primary/15">
      <div class="h-full bg-primary transition-[width]" :style="{ width: `${share}%` }" />
    </div>
  </div>
</template>

<script setup lang="ts">
/** The run bar while a run is queued or running: its step, its phase, and a progress line. */
import { computed } from 'vue'

import type { BenchmarkJob } from '@/api/types'
import Hint from '@/components/benchmark/Hint.vue'
import { runsListLocation } from '@/components/benchmark/report/routing'
import { Button } from '@/components/ui/button'
import { phaseText, planText, progressTitle } from './progress'

const props = defineProps<{
  job: BenchmarkJob
  cancelling: boolean
  nameOf: (id: string) => string
}>()

const emit = defineEmits<{ stop: [] }>()

const planTip = computed(() =>
  props.job.step_total ? planText(props.job.progress_plan, props.nameOf) : '',
)

const share = computed(() => {
  const { step_done: done, step_total: total } = props.job
  if (!total) return 0
  return Math.min(100, Math.round((done / total) * 100))
})
</script>
