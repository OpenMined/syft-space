<template>
  <BenchmarkResults v-if="view.kind === 'technical'" :slug="slug" />
  <RunReport
    v-else-if="view.kind === 'run'"
    :key="view.jobId"
    :slug="slug"
    :job-id="view.jobId"
    :screen="view.screen"
    :model-id="view.modelId"
  />
  <RunsList v-else :slug="slug" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import BenchmarkResults from '@/components/BenchmarkResults.vue'
import RunReport from './RunReport.vue'
import RunsList from './RunsList.vue'
import { provideRunReport } from './context'
import { readResultsView } from './routing'
import { useRunReport } from './useRunReport'

const props = defineProps<{ slug: string }>()

// One instance for the whole tab, so polling a running job survives list ↔ report navigation.
provideRunReport(useRunReport(() => props.slug))

const route = useRoute()
const view = computed(() => readResultsView(route.query))
</script>
