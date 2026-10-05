<template>
  <div class="space-y-3">
    <RouterLink
      :to="runsListLocation()"
      class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      data-testid="back-link"
    >
      <ArrowLeft class="size-4" aria-hidden="true" />
      Benchmark runs
    </RouterLink>

    <div
      class="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg border border-border bg-card px-4 py-3"
    >
      <div class="flex min-w-0 flex-[1_1_18rem] flex-wrap items-center gap-3">
        <Label for="report-run" class="text-sm font-medium">Run</Label>
        <Select :model-value="jobId" @update:model-value="pick">
          <SelectTrigger
            id="report-run"
            class="min-w-0 flex-1 sm:max-w-full sm:min-w-72 sm:flex-none"
          >
            <SelectValue class="min-w-0">
              <span class="truncate">{{ selectedLabel }}</span>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="o in options" :key="o.id" :value="o.id">{{ o.label }}</SelectItem>
          </SelectContent>
        </Select>
        <span
          v-if="!running"
          class="inline-flex basis-full items-center gap-2 text-sm text-muted-foreground sm:basis-auto"
          data-testid="visibility"
        >
          <span
            class="size-2 rounded-full"
            :class="published ? 'bg-primary' : 'bg-muted-foreground'"
            aria-hidden="true"
          />
          {{ published ? 'Published' : 'Private, only your team can see it' }}
        </span>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          :disabled="downloading || running"
          data-testid="download-summary"
          @click="download"
        >
          {{ downloading ? 'Downloading…' : 'Download summary' }}
        </Button>
        <Button
          v-if="published"
          variant="outline"
          :disabled="busy || running"
          data-testid="unpublish"
          @click="unpublish"
        >
          {{ busy ? 'Unpublishing…' : 'Unpublish' }}
        </Button>
        <Button v-else :disabled="busy || running" data-testid="publish" @click="publish">
          {{ busy ? 'Publishing…' : 'Publish scores' }}
        </Button>
      </div>
    </div>

    <p
      v-if="outdated"
      class="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground"
      data-testid="card-outdated"
    >
      <span class="inline-flex items-center gap-1.5">
        Published scores are out of date
        <InfoTip
          text="The figures changed after you published, for example after a verdict change."
        />
      </span>
      <Button
        variant="link"
        size="sm"
        class="h-auto px-0"
        :disabled="busy"
        data-testid="republish"
        @click="publish"
      >
        Republish
      </Button>
    </p>

    <p
      v-if="running"
      class="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground"
      data-testid="running-note"
    >
      {{ runningNote }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { ArrowLeft } from 'lucide-vue-next'
import type { AcceptableValue } from 'reka-ui'
import type { QualityMarketplaceResult } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiErrorDetail } from '@/lib/errors'
import InfoTip from '../InfoTip.vue'
import { useReport, useRun } from './context'
import { dayTime, windowText } from './figures'
import { runReportLocation, runsListLocation } from './routing'
import { progressText, utcStamp } from './selectors'

const props = defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const report = useReport()
const run = useRun()
const router = useRouter()
const busy = ref(false)
const downloading = ref(false)

const progress = computed(
  () => report.inProgress.value.find((p) => p.job_id === props.jobId) ?? null,
)
const running = computed(() => progress.value !== null)
const summary = computed(
  () => run.data.value?.run ?? report.runs.value.find((r) => r.job_id === props.jobId) ?? null,
)
const published = computed(() => summary.value?.published ?? false)
const outdated = computed(() => published.value && !!summary.value?.card_outdated && !running.value)
const runningNote = computed(() => {
  const step = progress.value ? progressText(progress.value) : ''
  return `This run is still in progress${step ? `: ${step}` : ''}. Results appear here when it finishes.`
})

function label(createdAt: string | null, windowDays: number | null | undefined): string {
  const when = dayTime(utcStamp(createdAt))
  const window = windowText(windowDays)
  return window ? `${when} · ${window}` : when
}

/** Finished runs of the list's current page, plus this one whatever its state. */
const options = computed(() => {
  const list = report.runs.value.map((r) => ({
    id: r.job_id,
    label: label(r.created_at, r.window_days),
  }))
  if (!list.some((o) => o.id === props.jobId)) {
    const own = summary.value
    const p = progress.value
    let text = 'This run'
    if (own) text = label(own.created_at, own.window_days)
    else if (p) text = label(p.created_at, null)
    list.unshift({ id: props.jobId, label: text })
  }
  return list
})

// Set explicitly: SelectValue keeps the first label it saw for a value.
const selectedLabel = computed(() => options.value.find((o) => o.id === props.jobId)?.label)

function pick(value: AcceptableValue): void {
  if (typeof value !== 'string' || value === props.jobId) return
  void router.push(runReportLocation(value, props.modelId))
}

/** Each marketplace that refused: its name and why. */
function refusedText(refused: QualityMarketplaceResult[]): string {
  return refused
    .map((r) => {
      const why = r.error || r.message
      return why ? `${r.marketplace_name}: ${why}` : r.marketplace_name
    })
    .join('; ')
}

async function publish(): Promise<void> {
  busy.value = true
  try {
    const { refused } = await report.publish(props.jobId)
    if (refused.length)
      toast.warning(`Published here; ${refused.length} marketplace(s) refused`, {
        description: refusedText(refused),
      })
    else toast.success('Published')
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not publish this run'))
  } finally {
    busy.value = false
  }
}

async function unpublish(): Promise<void> {
  busy.value = true
  try {
    const { refused } = await report.unpublish(props.jobId)
    if (refused.length)
      toast.warning(`Withdrawn here; ${refused.length} marketplace(s) refused`, {
        description: refusedText(refused),
      })
    else toast.success('Unpublished')
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not unpublish this run'))
  } finally {
    busy.value = false
  }
}

async function download(): Promise<void> {
  downloading.value = true
  try {
    await report.downloadSummary(props.jobId)
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not download the summary'))
  } finally {
    downloading.value = false
  }
}
</script>
