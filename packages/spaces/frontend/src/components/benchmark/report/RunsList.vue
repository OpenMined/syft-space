<template>
  <section class="space-y-5" aria-labelledby="runs-title">
    <div class="space-y-1">
      <h2 id="runs-title" class="heading-3">Benchmark runs</h2>
      <p v-if="schedule" class="text-sm text-muted-foreground" data-testid="schedule">
        {{ schedule }}
      </p>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="space-y-1.5">
        <Label for="runs-from" class="text-xs text-muted-foreground">From</Label>
        <Input
          id="runs-from"
          v-model="report.filters.from"
          type="date"
          class="w-40"
          data-testid="filter-from"
        />
      </div>
      <div class="space-y-1.5">
        <Label for="runs-to" class="text-xs text-muted-foreground">To</Label>
        <Input
          id="runs-to"
          v-model="report.filters.to"
          type="date"
          class="w-40"
          data-testid="filter-to"
        />
      </div>
      <div class="space-y-1.5">
        <Label for="runs-status" class="text-xs text-muted-foreground">Status</Label>
        <Select v-model="report.filters.status">
          <SelectTrigger id="runs-status" class="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">
              {{ o.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <Alert v-if="report.error.value" variant="destructive" data-testid="runs-error">
      <AlertDescription class="flex flex-wrap items-center justify-between gap-3">
        <span>{{ report.error.value }}</span>
        <Button variant="outline" size="sm" @click="report.refresh()">Try again</Button>
      </AlertDescription>
    </Alert>

    <div class="relative overflow-x-auto rounded-lg border border-border bg-card">
      <table class="w-full min-w-[720px] text-sm">
        <thead class="bg-muted/40 text-xs text-muted-foreground">
          <tr class="border-b border-border">
            <th scope="col" class="px-4 py-2.5 text-left font-medium">Run</th>
            <th scope="col" class="px-3 py-2.5 text-right font-medium">Articles</th>
            <th scope="col" class="px-3 py-2.5 text-right font-medium">Questions</th>
            <th scope="col" class="px-3 py-2.5 text-right font-medium">Models</th>
            <th scope="col" class="px-4 py-2.5 text-left font-medium">
              Lift from your data, in points
            </th>
            <th scope="col" class="px-3 py-2.5 text-left font-medium">Status</th>
            <th scope="col" class="w-10"><span class="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="run in running"
            :key="run.job_id"
            class="border-b border-border bg-muted/30 last:border-b-0"
            data-testid="run-in-progress"
          >
            <td class="px-4 py-3 align-top">
              <div class="font-medium tabular-nums">{{ dayTime(utcStamp(run.created_at)) }}</div>
              <div
                v-if="progressShare(run) !== null"
                class="mt-2 h-1 w-full max-w-48 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                :aria-valuenow="Math.round(progressShare(run)! * 100)"
                aria-valuemin="0"
                aria-valuemax="100"
                :aria-label="`Progress of the run of ${dayTime(utcStamp(run.created_at))}`"
              >
                <div
                  class="h-full rounded-full bg-primary transition-[width]"
                  :style="{ width: share(progressShare(run)!) }"
                />
              </div>
              <div class="mt-1.5 text-xs text-muted-foreground">
                {{ progressText(run) }}
              </div>
            </td>
            <td class="px-3 py-3 text-right text-muted-foreground">{{ DASH }}</td>
            <td class="px-3 py-3 text-right text-muted-foreground">{{ DASH }}</td>
            <td class="px-3 py-3 text-right text-muted-foreground">{{ DASH }}</td>
            <td class="px-4 py-3 text-muted-foreground">Results when the run finishes</td>
            <td class="px-3 py-3">
              <Badge variant="outline" class="border-primary text-primary">
                {{ run.state === 'queued' ? 'Queued' : 'Running' }}
              </Badge>
            </td>
            <td />
          </tr>

          <tr
            v-for="run in report.runs.value"
            :key="run.job_id"
            class="cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-muted/40"
            data-testid="run-row"
            @click="open(run.job_id)"
          >
            <td class="px-4 py-3">
              <RouterLink
                :to="runReportLocation(run.job_id)"
                class="font-medium tabular-nums hover:underline focus-visible:underline"
                @click.stop
              >
                {{ dayTime(utcStamp(run.created_at)) }}
              </RouterLink>
            </td>
            <td class="px-3 py-3 text-right tabular-nums">{{ count(run.articles) }}</td>
            <td class="px-3 py-3 text-right tabular-nums">{{ count(run.questions) }}</td>
            <td class="px-3 py-3 text-right tabular-nums">{{ count(run.models.length) }}</td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-3">
                <div
                  class="relative h-2 min-w-20 flex-1 overflow-hidden rounded-full bg-muted"
                  aria-hidden="true"
                >
                  <div
                    v-if="run.lift_lo !== null && run.lift_hi !== null"
                    class="absolute inset-y-0 min-w-1.5 rounded-full bg-primary"
                    :style="rangeStyle(run.lift_lo, run.lift_hi)"
                  />
                </div>
                <span class="w-28 shrink-0 font-semibold text-primary tabular-nums">
                  {{ pointsRange(run.lift_lo, run.lift_hi) }}
                </span>
              </div>
            </td>
            <td class="px-3 py-3">
              <Badge
                variant="outline"
                :class="
                  run.published
                    ? 'border-transparent bg-primary/10 text-primary'
                    : 'border-transparent bg-muted text-muted-foreground'
                "
              >
                {{ run.published ? 'Published' : 'Private' }}
              </Badge>
            </td>
            <td class="pr-3 text-muted-foreground">
              <ChevronRight class="size-4" aria-hidden="true" />
            </td>
          </tr>

          <tr v-if="report.loading.value && !report.loaded.value" data-testid="runs-loading">
            <td colspan="7" class="px-4 py-3">
              <span class="sr-only">Loading runs</span>
              <div class="space-y-3" aria-hidden="true">
                <Skeleton v-for="n in 3" :key="n" class="h-6" />
              </div>
            </td>
          </tr>
          <tr v-else-if="!report.runs.value.length && !running.length" data-testid="runs-empty">
            <td colspan="7" class="px-4 py-6 text-muted-foreground">
              {{
                report.filtered.value
                  ? 'No runs match these filters. Clear a filter to see more.'
                  : 'No runs yet.'
              }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="report.total.value > RUNS_PAGE"
      class="flex flex-wrap items-center justify-between gap-3 text-sm"
      data-testid="pager"
    >
      <span class="text-muted-foreground">
        Showing {{ first + 1 }}–{{ first + report.runs.value.length }} of
        {{ report.total.value }} runs
      </span>
      <div class="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          :disabled="report.page.value === 0"
          @click="report.page.value -= 1"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="first + RUNS_PAGE >= report.total.value"
          @click="report.page.value += 1"
        >
          Next
        </Button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronRight } from 'lucide-vue-next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useReport } from './context'
import { count, DASH, dayTime, pointsRange, scheduleText } from './figures'
import { runReportLocation } from './routing'
import { progressShare, progressText, utcStamp } from './selectors'
import { RUNS_PAGE } from './useRunReport'

defineProps<{ slug: string }>()

const STATUS_OPTIONS = [
  { value: 'all', label: 'All runs' },
  { value: 'private', label: 'Private' },
  { value: 'published', label: 'Published' },
] as const

const report = useReport()
const router = useRouter()

const schedule = computed(() => scheduleText(report.target.value))

/** Queued and running runs: listed first whatever the filters, never paged. */
const running = computed(() => report.inProgress.value)

const first = computed(() => report.page.value * RUNS_PAGE)

function clamp01(x: number): number {
  return Math.min(Math.max(x, 0), 1)
}

function share(x: number): string {
  return `${clamp01(x) * 100}%`
}

/** Lift on a 0–100 point scale; a negative end is drawn from zero. */
function rangeStyle(lo: number, hi: number): Record<string, string> {
  const left = clamp01(lo / 100)
  return { left: share(left), width: share(Math.max(clamp01(hi / 100) - left, 0)) }
}

function open(jobId: string): void {
  void router.push(runReportLocation(jobId))
}
</script>
