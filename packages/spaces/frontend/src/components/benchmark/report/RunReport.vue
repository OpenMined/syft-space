<template>
  <div class="space-y-8">
    <ReportRunBar v-bind="sectionProps" />
    <template v-if="!running">
      <Alert v-if="error" variant="destructive" data-testid="run-error">
        <AlertDescription class="flex flex-wrap items-center justify-between gap-3">
          <span>{{ error }}</span>
          <Button variant="outline" size="sm" @click="reload">Try again</Button>
        </AlertDescription>
      </Alert>
      <div v-if="data" class="space-y-8">
        <ReportSummary v-bind="sectionProps" />
        <ReportModels v-bind="sectionProps" />
        <div class="grid grid-cols-1 gap-8 *:min-w-0 lg:grid-cols-2">
          <ReportAnswered v-bind="sectionProps" />
          <ReportKinds v-bind="sectionProps" />
        </div>
        <ReportChecks v-bind="sectionProps" />
        <ReportQuestions v-bind="sectionProps" />
        <ReportMethod v-bind="sectionProps" />
        <RouterLink
          :to="technicalLocation()"
          class="inline-block text-sm text-primary underline-offset-4 hover:underline"
          data-testid="technical-link"
        >
          Full technical breakdown for researchers
        </RouterLink>
      </div>
      <div v-else-if="!error" class="space-y-4" aria-busy="true" data-testid="run-loading">
        <span class="sr-only">Loading this run</span>
        <Skeleton class="h-6 w-40" />
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Skeleton v-for="n in 4" :key="n" class="h-24" />
        </div>
        <Skeleton class="h-48" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { BenchmarkRunReport } from '@/api/types'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorDetail } from '@/lib/errors'
import ReportAnswered from './ReportAnswered.vue'
import ReportChecks from './ReportChecks.vue'
import ReportKinds from './ReportKinds.vue'
import ReportMethod from './ReportMethod.vue'
import ReportModels from './ReportModels.vue'
import ReportQuestions from './ReportQuestions.vue'
import ReportRunBar from './ReportRunBar.vue'
import ReportSummary from './ReportSummary.vue'
import { provideRun, useReport } from './context'
import { runReportLocation, technicalLocation } from './routing'

const props = defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const report = useReport()
const router = useRouter()
const data = shallowRef<BenchmarkRunReport | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const running = computed(() => report.isRunning(props.jobId))

async function reload(): Promise<void> {
  if (running.value) return
  loading.value = true
  error.value = null
  try {
    data.value = await report.loadReport(props.jobId)
  } catch (e) {
    error.value = apiErrorDetail(e, 'Could not load this run')
  } finally {
    loading.value = false
  }
}

watch([() => report.revision.value, running], reload, { immediate: true })

const model = computed(() => {
  const models = data.value?.models.map((m) => m.model) ?? []
  if (props.modelId && models.includes(props.modelId)) return props.modelId
  return models[0] ?? props.modelId
})

const modelReport = computed(() => data.value?.models.find((m) => m.model === model.value) ?? null)

function selectModel(id: string): void {
  void router.replace(runReportLocation(props.jobId, id))
}

const kind = ref<string | null>(null)
function setKind(k: string | null): void {
  kind.value = k
}

provideRun({
  jobId: props.jobId,
  data,
  loading,
  error,
  running,
  model,
  modelReport,
  selectModel,
  kind,
  setKind,
  reload,
})

const sectionProps = computed(() => ({
  slug: props.slug,
  jobId: props.jobId,
  modelId: model.value,
}))
</script>
