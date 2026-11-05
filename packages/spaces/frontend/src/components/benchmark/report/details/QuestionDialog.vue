<script setup lang="ts">
/** Details of one question for one model: each arm's calls, checks and judges, and how it was made. */
import { computed, ref, shallowRef, watch } from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkResult } from '@/api/types'
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { apiErrorDetail } from '@/lib/errors'
import { useReport, useRun } from '../context'
import { kindLabel } from '../../kinds'
import { modelName } from '../labels'
import ArmPanel from './ArmPanel.vue'
import { allPages } from './load'
import QuestionOrigin from './QuestionOrigin.vue'
import { ARM_TITLE, auditOf } from './questionAudit'

const props = defineProps<{
  qaId: string
  question: string
  generator: string
}>()

const open = defineModel<boolean>('open', { required: true })

/** Rows per request: with prompts each row carries the full audit trail. */
const PAGE = 100

const report = useReport()
const run = useRun()

const model = computed(() => run.model.value ?? '')
const rows = shallowRef<BenchmarkResult[] | null>(null)
const error = ref<string | null>(null)
let request = 0

async function load(): Promise<void> {
  const mine = ++request
  error.value = null
  try {
    const query = { qa_id: props.qaId, model: model.value, job: run.jobId, prompts: true }
    const all = await allPages(
      (offset, limit) => benchmarksApi.listResults(run.slug, { ...query, limit, offset }),
      PAGE,
    )
    if (mine === request) rows.value = all
  } catch (e) {
    if (mine === request) error.value = apiErrorDetail(e, 'Could not load this question')
  }
}

watch(
  [open, () => props.qaId, model],
  ([shown]) => {
    rows.value = null
    if (shown) void load()
  },
  { immediate: true },
)

const panel = computed(() => run.data.value?.judges ?? [])
const arms = computed(() => (rows.value ? auditOf(rows.value, panel.value) : []))
const tab = ref<string | undefined>(undefined)
const originShown = ref(false)

watch(arms, (list) => {
  if (!list.some((a) => a.arm === tab.value)) tab.value = list[0]?.arm
})

/** Reload this question and every figure of the run. */
async function changed(): Promise<void> {
  await load()
  report.invalidate(run.jobId)
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogScrollContent class="sm:max-w-5xl" data-testid="question-dialog">
      <DialogHeader class="pr-8">
        <DialogTitle class="text-base leading-snug break-words">{{ question }}</DialogTitle>
        <DialogDescription>{{ kindLabel(generator) }} · {{ modelName(model) }}</DialogDescription>
      </DialogHeader>

      <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
      <div v-else-if="!rows" aria-busy="true" class="space-y-3">
        <span class="sr-only">Loading</span>
        <Skeleton class="h-8 w-60" />
        <Skeleton class="h-48" />
      </div>
      <p v-else-if="!arms.length" class="text-sm text-muted-foreground">
        This model has no answers to this question.
      </p>
      <Tabs v-else v-model="tab">
        <TabsList>
          <TabsTrigger
            v-for="arm in arms"
            :key="arm.arm"
            :value="arm.arm"
            :data-testid="`tab-${arm.arm}`"
            >{{ ARM_TITLE[arm.arm] ?? arm.arm }}</TabsTrigger
          >
        </TabsList>
        <TabsContent v-for="arm in arms" :key="arm.arm" :value="arm.arm" class="pt-3">
          <ArmPanel
            :arm="arm"
            :model="model"
            :generator="generator"
            :panel="panel"
            :slug="run.slug"
            @changed="changed"
          />
        </TabsContent>
      </Tabs>

      <details
        class="border-t border-border pt-3"
        data-testid="origin-section"
        @toggle="originShown = ($event.target as HTMLDetailsElement).open"
      >
        <summary class="cursor-pointer text-sm font-semibold">How this question was made</summary>
        <QuestionOrigin
          v-if="originShown"
          class="pt-3"
          :slug="run.slug"
          :job-id="run.jobId"
          :qa-id="qaId"
        />
      </details>
    </DialogScrollContent>
  </Dialog>
</template>
