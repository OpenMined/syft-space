<template>
  <section v-if="data" class="space-y-6" data-testid="screen-RunSummaryPage">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-0.5">
        <div class="flex flex-wrap items-center gap-2.5">
          <h1 class="heading-3">Run of {{ dayTime(utcStamp(data.run.created_at)) }}</h1>
          <Badge variant="outline" :class="published ? PUBLISHED_TONE : PRIVATE_TONE">
            {{ published ? 'Published' : 'Private' }}
          </Badge>
        </div>
        <p v-if="articles" class="text-sm text-muted-foreground" data-testid="run-articles">
          {{ articles }}
        </p>
      </div>
      <div v-if="!buildOnly" class="flex flex-wrap gap-2">
        <Button
          variant="outline"
          :disabled="downloading"
          data-testid="download-summary"
          @click="download"
        >
          Download summary
        </Button>
        <Button v-if="!published" :disabled="publishing" data-testid="publish" @click="publish">
          Publish scores
        </Button>
      </div>
    </div>

    <p
      v-if="justPublished"
      role="status"
      class="rounded-md bg-primary/10 px-3.5 py-2.5 text-sm text-primary"
      data-testid="published-note"
    >
      Published. Scores from this run are now public; questions and articles stay private.
    </p>

    <div
      class="flex flex-wrap items-center gap-x-4 gap-y-2.5 rounded-lg border border-border bg-card px-4 py-3 text-sm"
      data-testid="funnel"
    >
      <span
        ><b class="font-semibold">{{ count(data.funnel.written) }}</b> questions written</span
      >
      <span class="text-muted-foreground" aria-hidden="true">→</span>
      <span>
        <b
          class="font-semibold"
          :class="removed === null ? 'text-muted-foreground' : 'text-amber-700 dark:text-amber-400'"
          data-testid="funnel-removed"
          >{{ count(removed) }}</b
        >
        removed because a model with web search could already answer them
      </span>
      <span class="text-muted-foreground" aria-hidden="true">→</span>
      <span>
        <b class="font-semibold text-primary">{{ count(data.funnel.asked) }}</b> asked to each model
      </span>
    </div>

    <BuildPhases v-if="buildOnly && slug" :slug="slug" :job="jobId" />

    <section v-if="!buildOnly" class="space-y-2.5" aria-labelledby="models-title">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="models-title" class="text-base font-semibold">How each model did</h2>
          <p class="text-sm text-muted-foreground" data-testid="models-lead">{{ lead }}</p>
        </div>
        <div class="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span class="flex items-center gap-1.5">
            <i class="inline-block size-2.5 rounded-sm bg-primary" aria-hidden="true" />
            With your data
          </span>
          <span class="flex items-center gap-1.5">
            <i class="inline-block size-2.5 rounded-sm bg-muted-foreground/60" aria-hidden="true" />
            On its own
          </span>
        </div>
      </div>

      <div class="overflow-hidden rounded-lg border border-border bg-card">
        <RouterLink
          v-for="m in data.models"
          :key="m.model"
          :to="modelLocation(jobId, m.model)"
          class="flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-border px-5 py-4 transition-colors last:border-b-0 hover:bg-muted/40"
          data-testid="model-row"
        >
          <span class="flex min-w-0 flex-1 flex-col md:flex-[0_0_11.25rem]">
            <b class="font-semibold">{{ modelName(m.model) }}</b>
            <span v-if="vendorName(m.model)" class="text-xs text-muted-foreground">
              {{ vendorName(m.model) }}
            </span>
          </span>
          <span
            class="order-3 flex basis-full flex-col gap-2 md:order-none md:flex-[1_1_23.75rem] md:basis-auto"
          >
            <span class="flex flex-wrap items-center gap-x-3 gap-y-1 md:flex-nowrap">
              <span
                class="block h-2.5 basis-full overflow-hidden rounded bg-muted md:flex-1 md:basis-auto"
                aria-hidden="true"
              >
                <span
                  class="block h-full rounded bg-primary"
                  :style="{ width: width(m.rate_with) }"
                />
              </span>
              <span class="text-sm md:w-[13.5rem] md:shrink-0" data-testid="right-with">
                <b class="font-semibold">{{ ofText(m.right_with, m.graded_with) }}</b> right with
                your data
              </span>
            </span>
            <span class="flex flex-wrap items-center gap-x-3 gap-y-1 md:flex-nowrap">
              <span
                class="block h-2.5 basis-full overflow-hidden rounded bg-muted md:flex-1 md:basis-auto"
                aria-hidden="true"
              >
                <span
                  class="block h-full rounded bg-muted-foreground/60"
                  :style="{ width: width(m.rate_alone) }"
                />
              </span>
              <span
                class="text-sm text-muted-foreground md:w-[13.5rem] md:shrink-0"
                data-testid="right-alone"
              >
                {{ ofText(m.right_alone, m.graded_alone) }} on its own
              </span>
            </span>
          </span>
          <span class="flex flex-col items-end md:w-24">
            <b class="text-xl font-semibold text-primary tabular-nums">{{ points(m.lift) }}</b>
            <span class="text-xs text-muted-foreground">points</span>
          </span>
          <ChevronRight class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </RouterLink>
      </div>
    </section>

    <RouterLink
      :to="methodLocation(jobId)"
      class="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3.5 transition-colors hover:bg-muted/40"
      data-testid="method-link"
    >
      <span class="flex flex-col gap-0.5">
        <b class="font-medium">How this was tested</b>
        <span class="text-xs text-muted-foreground">
          The settings this run used: how questions were written and filtered, which models and
          judges took part, and what left your organization
        </span>
      </span>
      <ChevronRight class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
    </RouterLink>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import { ChevronRight } from 'lucide-vue-next'
import type { QualityMarketplaceResult } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import BuildPhases from '../BuildPhases.vue'
import { apiErrorDetail } from '@/lib/errors'
import { useReport, useRun } from './context'
import { count, DASH, dayTime, points } from './figures'
import { modelName, vendorName } from './labels'
import { methodLocation, modelLocation } from './routing'
import { articlesText, utcStamp, webRemoved } from './selectors'

const PUBLISHED_TONE = 'border-transparent bg-primary/10 text-primary'
const PRIVATE_TONE = 'border-transparent bg-muted text-muted-foreground'

const report = useReport()
const { jobId, slug, data } = useRun()

const published = computed(() => data.value?.run.published ?? false)
/** No model was asked: the page shows what the job wrote and filtered. */
const buildOnly = computed(() => data.value?.run.build_only ?? false)
const articles = computed(() => (data.value ? articlesText(data.value) : null))
const removed = computed(() => (data.value ? webRemoved(data.value) : null))

/** Unsigned whole points: 47 → `47`, −5 → `−5`. */
function bare(x: number): string {
  const n = Math.round(x)
  return n < 0 ? `−${-n}` : String(n)
}

const lead = computed(() => {
  const lifts = (data.value?.models ?? [])
    .map((m) => m.lift)
    .filter((x): x is number => typeof x === 'number')
  const tail = 'Select a model to see how it answered.'
  if (!lifts.length) return tail
  const lo = bare(Math.min(...lifts))
  const hi = bare(Math.max(...lifts))
  return `Your data added ${lo === hi ? lo : `${lo} to ${hi}`} points. ${tail}`
})

function width(rate: number | null): string {
  return `${Math.min(Math.max(rate ?? 0, 0), 1) * 100}%`
}

function ofText(right: number, graded: number): string {
  return graded > 0 ? `${count(right)} of ${count(graded)}` : DASH
}

const downloading = ref(false)
const publishing = ref(false)
const justPublished = ref(false)

async function download(): Promise<void> {
  downloading.value = true
  try {
    await report.downloadSummary(jobId)
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not download the summary'))
  } finally {
    downloading.value = false
  }
}

function refusedText(refused: QualityMarketplaceResult[]): string {
  return refused
    .map((r) => {
      const why = r.error || r.message
      return why ? `${r.marketplace_name}: ${why}` : r.marketplace_name
    })
    .join('; ')
}

async function publish(): Promise<void> {
  publishing.value = true
  try {
    const { refused } = await report.publish(jobId)
    justPublished.value = true
    if (refused.length)
      toast.warning(`${refused.length} marketplace(s) refused the scores`, {
        description: refusedText(refused),
      })
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not publish this run'))
  } finally {
    publishing.value = false
  }
}
</script>
