<template>
  <section class="space-y-5" aria-labelledby="runs-title">
    <div class="space-y-1">
      <h1 id="runs-title" class="heading-3">Benchmark runs</h1>
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
            <th scope="col" class="w-20"><span class="sr-only">Actions</span></th>
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
              <div class="font-semibold tabular-nums">{{ dayTime(utcStamp(run.created_at)) }}</div>
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
                  :style="{ width: barWidth(progressShare(run)) }"
                />
              </div>
              <Hint :text="planText(run.progress_plan, modelName)">
                <div class="mt-1.5 text-xs text-muted-foreground">
                  {{ progressText(run) }}
                </div>
              </Hint>
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
                :to="runLocation(run.job_id)"
                class="font-semibold tabular-nums hover:underline focus-visible:underline"
                @click.stop
              >
                {{ dayTime(utcStamp(run.created_at)) }}
              </RouterLink>
            </td>
            <td class="px-3 py-3 text-right tabular-nums">{{ count(run.articles) }}</td>
            <td class="px-3 py-3 text-right tabular-nums">{{ count(run.questions) }}</td>
            <td class="px-3 py-3 text-right tabular-nums">
              {{ run.build_only ? DASH : count(run.models.length) }}
            </td>
            <td
              v-if="run.build_only"
              class="px-4 py-3 text-muted-foreground"
              data-testid="run-build"
            >
              {{ buildText(run.build) ?? DASH }}
            </td>
            <td v-else class="px-4 py-3">
              <div class="flex items-center gap-3">
                <div
                  class="relative h-2 min-w-20 flex-1 overflow-hidden rounded-full bg-muted"
                  aria-hidden="true"
                >
                  <div
                    v-if="run.lift_lo !== null && run.lift_hi !== null"
                    class="absolute inset-y-0 min-w-1.5 rounded-full bg-primary"
                    :style="liftStyle(run.lift_hi)"
                  />
                </div>
                <span class="w-28 shrink-0 font-semibold text-primary tabular-nums">
                  {{ pointsRange(run.lift_lo, run.lift_hi) }}
                </span>
              </div>
            </td>
            <td class="space-x-1.5 whitespace-nowrap px-3 py-3">
              <AlertBadge
                v-if="!run.build_only && stoppedLabel(run)"
                :tip="stoppedTip(run)"
                data-testid="run-stopped"
              >
                {{ stoppedLabel(run) }}
              </AlertBadge>
              <Hint
                v-if="runStateLabel(run)"
                :text="run.build_only ? (stoppedTip(run) ?? BUILD_ONLY_TIP) : null"
              >
                <Badge
                  variant="outline"
                  class="border-transparent bg-muted text-muted-foreground"
                  data-testid="run-state"
                >
                  {{ runStateLabel(run) }}
                </Badge>
              </Hint>
            </td>
            <td class="pr-3 text-muted-foreground">
              <div class="flex items-center justify-end gap-1">
                <Hint text="Delete this run">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7 text-muted-foreground hover:text-destructive"
                    aria-label="Delete this run"
                    data-testid="run-delete"
                    @click.stop="askDelete(run)"
                  >
                    <Trash2 class="size-4" />
                  </Button>
                </Hint>
                <ChevronRight class="size-4" aria-hidden="true" />
              </div>
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
      v-if="report.total.value > 0"
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

    <DeleteConfirmationDialog
      :open="toDelete !== null"
      item-type="run"
      :item-name="toDelete ? dayTime(utcStamp(toDelete.created_at)) : ''"
      :description="DELETE_TEXT"
      :is-deleting="deleting"
      @update:open="(open) => !open && !deleting && (toDelete = null)"
      @confirm="confirmDelete"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronRight, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { BenchmarkRunSummary } from '@/api/types'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorDetail } from '@/lib/errors'
import Hint from '../Hint.vue'
import AlertBadge from './AlertBadge.vue'
import { useReport } from './context'
import { barWidth, count, DASH, dayTime, pointsRange, scheduleText, utcStamp } from './figures'
import { modelName } from './labels'
import { runLocation } from './routing'
import { planText } from '../setup/progress'
import { buildText } from '../filter'
import { progressShare, progressText, runStateLabel, stoppedLabel, stoppedTip } from './selectors'
import { RUNS_PAGE } from './useRunReport'

const BUILD_ONLY_TIP = 'Questions were written and filtered; no model was asked.'
const DELETE_TEXT =
  'The run and its answers will be deleted; its questions are kept. This cannot be undone.'

const report = useReport()
const router = useRouter()

const schedule = computed(() => scheduleText(report.target.value))

/** Queued and running runs: listed first whatever the filters, never paged. */
const running = computed(() => report.inProgress.value)

const first = computed(() => report.page.value * RUNS_PAGE)

/** Lift on a 0–100 point scale, drawn from zero to the top of the range. */
function liftStyle(hi: number): Record<string, string> {
  return { left: '0%', width: barWidth(hi / 100) }
}

function open(jobId: string): void {
  void router.push(runLocation(jobId))
}

const toDelete = ref<BenchmarkRunSummary | null>(null)
const deleting = ref(false)

function askDelete(run: BenchmarkRunSummary): void {
  toDelete.value = run
}

async function confirmDelete(): Promise<void> {
  const run = toDelete.value
  if (!run || deleting.value) return
  deleting.value = true
  try {
    await report.deleteRun(run.job_id)
    toDelete.value = null
    toast.success('Run deleted')
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not delete the run'))
  } finally {
    deleting.value = false
  }
}
</script>
