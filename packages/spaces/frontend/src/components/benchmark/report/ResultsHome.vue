<template>
  <div class="space-y-2">
    <div class="flex justify-end">
      <Hint text="Show the prompts, replies and verdicts behind the figures." :focusable="false">
        <label class="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
          <Checkbox v-model="details" data-testid="details-toggle" />
          Details
        </label>
      </Hint>
    </div>
    <RunReport
      v-if="view.kind === 'run'"
      :key="view.jobId"
      :slug="slug"
      :job-id="view.jobId"
      :screen="view.screen"
      :model-id="view.modelId"
    />
    <RunsList v-else />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Checkbox } from '@/components/ui/checkbox'
import Hint from '../Hint.vue'
import RunReport from './RunReport.vue'
import RunsList from './RunsList.vue'
import { provideRunReport } from './context'
import { useDetails } from './details/useDetails'
import { readResultsView } from './routing'
import { useRunReport } from './useRunReport'

const props = defineProps<{ slug: string }>()

// One instance for the whole tab, so polling a running job survives list ↔ report navigation.
provideRunReport(useRunReport(() => props.slug))

const route = useRoute()
const view = computed(() => readResultsView(route.query))
const details = useDetails()
</script>
