<template>
  <div class="space-y-6">
    <ReportCrumbs :crumbs="crumbs" />
    <Alert v-if="running" data-testid="run-running">
      <AlertDescription
        >This run is still in progress. Results appear here when it finishes.</AlertDescription
      >
    </Alert>
    <template v-else>
      <Alert v-if="error" variant="destructive" data-testid="run-error">
        <AlertDescription class="flex flex-wrap items-center justify-between gap-3">
          <span>{{ error }}</span>
          <Button variant="outline" size="sm" @click="reload">Try again</Button>
        </AlertDescription>
      </Alert>
      <component :is="SCREENS[screen]" v-if="data" />
      <div v-else-if="!error" class="space-y-4" aria-busy="true" data-testid="run-loading">
        <span class="sr-only">Loading this run</span>
        <Skeleton class="h-6 w-60" />
        <Skeleton class="h-48" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch, type Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import type { BenchmarkRunReport } from '@/api/types'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorDetail } from '@/lib/errors'
import ChecksPage from './ChecksPage.vue'
import ModelPage from './ModelPage.vue'
import QuestionsPage from './QuestionsPage.vue'
import ReportCrumbs from './ReportCrumbs.vue'
import RunMethodPage from './RunMethodPage.vue'
import RunSummaryPage from './RunSummaryPage.vue'
import { provideRun, useReport } from './context'
import { day as dayOf } from './figures'
import { modelName } from './labels'
import { utcStamp } from './selectors'
import { modelLocation, runLocation, runsListLocation, type RunScreen } from './routing'

const props = defineProps<{
  slug: string
  jobId: string
  screen: RunScreen
  modelId: string | null
}>()

const SCREENS: Record<RunScreen, Component> = {
  run: RunSummaryPage,
  method: RunMethodPage,
  model: ModelPage,
  questions: QuestionsPage,
  checks: ChecksPage,
}

const report = useReport()
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

const model = computed(() => props.modelId)
const modelReport = computed(() => data.value?.models.find((m) => m.model === model.value) ?? null)

provideRun({
  jobId: props.jobId,
  slug: props.slug,
  data,
  loading,
  error,
  running,
  model,
  modelReport,
  reload,
})

const SCREEN_TITLE: Partial<Record<RunScreen, string>> = {
  method: 'How this was tested',
  questions: 'Every question and answer',
  checks: 'Reliability checks',
}

const crumbs = computed(() => {
  const created =
    data.value?.run.created_at ??
    report.runs.value.find((r) => r.job_id === props.jobId)?.created_at
  const day = dayOf(utcStamp(created))
  const list: { label: string; to?: RouteLocationRaw }[] = [
    { label: 'Benchmark runs', to: runsListLocation() },
    { label: day ? `Run of ${day}` : 'Run', to: runLocation(props.jobId) },
  ]
  if (props.modelId)
    list.push({ label: modelName(props.modelId), to: modelLocation(props.jobId, props.modelId) })
  const title = SCREEN_TITLE[props.screen]
  if (title) list.push({ label: title })
  return list
})
</script>
