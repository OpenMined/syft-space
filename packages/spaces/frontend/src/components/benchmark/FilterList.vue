<script setup lang="ts">
/** Every filter decision one job made, with the web check behind it on demand. */
import { reactive, ref, watch } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { apiErrorDetail } from '@/lib/errors'
import type { BenchmarkFilterDecision, BenchmarkFilterOutcome } from '@/api/types'
import {
  countsText,
  hasDetails,
  hostOf,
  outcomeLabel,
  outcomeTone,
  reasonText,
  safeUrl,
  stageLabel,
  writtenInText,
} from './filter'
import { generatorWords } from './labels'
import { modelName } from './report/labels'
import { sortQuestions } from './questionOrder'

const props = defineProps<{ slug: string; job: string; refreshKey?: number }>()

const PAGE = 200
const MAX_FETCH = 1000
const items = ref<BenchmarkFilterDecision[]>([])
const total = ref(0)
const counts = ref<Partial<Record<BenchmarkFilterOutcome, number>>>({})
const loading = ref(false)
const truncated = ref(false)
const open = reactive<Record<string, boolean>>({})

async function load(): Promise<void> {
  loading.value = true
  try {
    const first = await benchmarksApi.listRunFilter(props.slug, props.job, {
      limit: PAGE,
      offset: 0,
    })
    const all = first.items.slice()
    let offset = PAGE
    while (offset < first.total && offset < MAX_FETCH) {
      const page = await benchmarksApi.listRunFilter(props.slug, props.job, {
        limit: PAGE,
        offset,
      })
      all.push(...page.items)
      offset += PAGE
    }
    items.value = sortQuestions(all, (d) => ({
      generator: d.generator,
      createdAt: d.written_at,
      id: d.qa_id,
    }))
    total.value = first.total
    counts.value = first.counts ?? {}
    truncated.value = first.total > all.length
  } catch (error) {
    toast.error(apiErrorDetail(error, 'Could not load filter decisions'))
  } finally {
    loading.value = false
  }
}

watch([() => props.job, () => props.refreshKey], load, { immediate: true })

function rowKey(d: BenchmarkFilterDecision, n: number): string {
  return `${d.qa_id}-${d.stage}-${d.at ?? n}`
}

function toggle(key: string): void {
  open[key] = !open[key]
}
</script>

<template>
  <div class="space-y-2" data-testid="filter-list">
    <p class="text-xs text-muted-foreground">
      {{ countsText(counts) || `${total} decision(s)` }}
      <span v-if="truncated">— showing the first {{ items.length }}</span>
    </p>
    <p v-if="loading && items.length === 0" class="text-sm text-muted-foreground">Loading…</p>
    <p v-else-if="items.length === 0" class="text-sm text-muted-foreground">Nothing here yet.</p>
    <ul v-else class="space-y-1.5">
      <li
        v-for="(d, n) in items"
        :key="rowKey(d, n)"
        class="rounded-md border border-border/60 p-2.5 text-sm space-y-1"
        data-testid="filter-row"
      >
        <div class="flex items-start gap-2">
          <button
            v-if="hasDetails(d.web_check)"
            type="button"
            class="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
            :aria-expanded="Boolean(open[rowKey(d, n)])"
            aria-label="Web check details"
            data-testid="filter-toggle"
            @click="toggle(rowKey(d, n))"
          >
            <ChevronRight
              class="h-3.5 w-3.5 transition-transform"
              :class="{ 'rotate-90': open[rowKey(d, n)] }"
            />
          </button>
          <span v-else class="w-3.5 shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="font-medium break-words text-foreground">{{ d.question }}</p>
            <p class="text-xs text-muted-foreground">
              {{ generatorWords(d.generator).label }} · {{ stageLabel(d.stage) }}
              <span v-if="writtenInText(d)" data-testid="written-in">
                · {{ writtenInText(d) }}
              </span>
            </p>
          </div>
          <span class="shrink-0 rounded px-1.5 py-0.5 text-xs" :class="outcomeTone(d.outcome)">
            {{ outcomeLabel(d.outcome) }}
          </span>
        </div>
        <p v-if="reasonText(d)" class="pl-5.5 text-xs text-muted-foreground italic break-words">
          {{ reasonText(d) }}
        </p>

        <dl
          v-if="d.web_check && open[rowKey(d, n)]"
          class="ml-5.5 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1.5 rounded-md bg-muted/30 p-2.5 text-xs"
          data-testid="filter-details"
        >
          <template v-if="d.web_check.model">
            <dt class="text-muted-foreground">Checked by</dt>
            <dd>
              {{ modelName(d.web_check.model) }}
              <template v-if="d.web_check.judge">
                · judged by {{ modelName(d.web_check.judge) }}
              </template>
            </dd>
          </template>
          <template v-if="d.web_check.answer">
            <dt class="text-muted-foreground">Web answer</dt>
            <dd class="break-words whitespace-pre-line">{{ d.web_check.answer }}</dd>
          </template>
          <template v-if="d.web_check.verdict">
            <dt class="text-muted-foreground">Verdict</dt>
            <dd>{{ d.web_check.verdict }}</dd>
          </template>
          <template v-if="d.web_check.reasoning">
            <dt class="text-muted-foreground">Judge reasoning</dt>
            <dd class="break-words whitespace-pre-line">{{ d.web_check.reasoning }}</dd>
          </template>
          <template v-if="d.web_check.citations?.length">
            <dt class="text-muted-foreground">Links</dt>
            <dd class="flex flex-wrap gap-x-2 gap-y-0.5" data-testid="filter-citations">
              <a
                v-for="(cite, i) in d.web_check.citations"
                :key="`${i}-${cite.url}`"
                :href="safeUrl(cite.url)"
                target="_blank"
                rel="noopener noreferrer"
                class="max-w-60 truncate text-primary hover:underline"
                :title="cite.url"
                >{{ cite.title || hostOf(cite.url) }}</a
              >
            </dd>
          </template>
          <template v-if="d.web_check.searches !== null">
            <dt class="text-muted-foreground">Searches</dt>
            <dd>{{ d.web_check.searches }}</dd>
          </template>
          <template v-if="d.web_check.error">
            <dt class="text-muted-foreground">Error</dt>
            <dd class="break-words text-destructive">{{ d.web_check.error }}</dd>
          </template>
        </dl>
      </li>
    </ul>
  </div>
</template>
