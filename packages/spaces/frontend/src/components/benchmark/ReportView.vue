<script setup lang="ts">
/**
 * The full, owner's-own reading of one endpoint's measured quality.
 *
 * Not the card that goes to the hub — same numbers, but read for the owner
 * who has to decide whether to trust and publish them: reasons spelled out
 * in words rather than left as codes (`trust.doubts`, only ever present on
 * this console's own build — see `owner_payload_for` in syft_benchmark).
 */
import { computed } from 'vue'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip as ChartTooltip,
  type TooltipItem,
} from 'chart.js'
import { Bar } from 'vue-chartjs'
import { CheckCircle2, TriangleAlert } from 'lucide-vue-next'
import { armWords, generatorWords, trustFlagWords } from './labels'
import { formatTimeAgo } from '@/lib/formatters'
import type { BenchmarkReport } from '@/api/types'

ChartJS.register(CategoryScale, LinearScale, BarElement, ChartTooltip, Legend)

const props = defineProps<{ report: BenchmarkReport }>()

// Only the owner's own build carries prose reasons (`doubts`) — a published
// card carries just the codes, worded again here from the same map
// `BenchmarkPanel.vue` uses for the published card, as a fallback rather
// than showing nothing once a report has been published.
const doubts = computed(
  () =>
    props.report.trust?.doubts ??
    props.report.trust?.flags.map((code) => trustFlagWords(code).label) ??
    [],
)

const scoreLabel = computed(
  () => props.report.score_label ?? (props.report.kind === 'retrieval' ? 'finds' : 'correct'),
)
const scorePct = computed(() =>
  props.report.score == null ? null : Math.round(props.report.score * 100),
)
const freshness = computed(() =>
  props.report.checked_at ? formatTimeAgo(props.report.checked_at) : '',
)

const answerable = computed(() => props.report.answerable)
const control = computed(() => props.report.unanswerable)

const PCT_TICKS = { color: '#9ca3af', font: { size: 11 }, callback: (v: string | number) => `${v}%` }
const GRID = { color: 'rgba(255,255,255,0.08)' }

function pctBarOptions() {
  return {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: { label: (ctx: TooltipItem<'bar'>) => `${ctx.parsed.x}%` },
      },
    },
    scales: {
      x: { min: 0, max: 100, ticks: PCT_TICKS, grid: GRID, border: { display: false } },
      y: {
        ticks: { color: '#9ca3af', font: { size: 11 } },
        grid: { display: false },
        border: { display: false },
      },
    },
  }
}

const distributionData = computed(() => {
  const a = answerable.value
  if (!a) return null
  return {
    labels: ['Correct', 'Abstained', 'Hallucinated'],
    datasets: [
      {
        data: [
          Math.round(a.correct * 100),
          Math.round(a.abstain * 100),
          Math.round(a.hallucinate * 100),
        ],
        backgroundColor: ['#10b981', '#9ca3af', '#ef4444'],
        borderRadius: 6,
        barPercentage: 0.6,
      },
    ],
  }
})

const modelsSorted = computed(() => [...props.report.models].sort((a, b) => b.accuracy - a.accuracy))
const modelsChartData = computed(() => ({
  labels: modelsSorted.value.map((m) => m.model),
  datasets: [
    {
      data: modelsSorted.value.map((m) => Math.round(m.accuracy * 100)),
      backgroundColor: '#3b82f6',
      borderRadius: 6,
      barPercentage: 0.6,
    },
  ],
}))
// Chart.js sizes a horizontal bar chart's height from its container, not
// from its row count — without this, nine models draw as nine slivers in
// the same box that fits three.
const modelsChartHeight = computed(() => Math.max(120, modelsSorted.value.length * 32))

const skillsSorted = computed(() => [...props.report.skills].sort((a, b) => b.accuracy - a.accuracy))
const skillsChartData = computed(() => ({
  labels: skillsSorted.value.map((s) => generatorWords(s.generator).label),
  datasets: [
    {
      data: skillsSorted.value.map((s) => Math.round(s.accuracy * 100)),
      backgroundColor: '#2dd4bf',
      borderRadius: 6,
      barPercentage: 0.6,
    },
  ],
}))
const skillsChartHeight = computed(() => Math.max(120, skillsSorted.value.length * 32))

function pct(value: number | null | undefined): string {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function contextGainWords(gain: number | null): string {
  if (gain == null) return ''
  if (gain < 0) return 'context made it more willing to say "I don\'t know"'
  if (gain > 0) return 'context made it less willing to say "I don\'t know"'
  return 'context changed nothing about when it abstains'
}
</script>

<template>
  <div class="space-y-5 text-sm">
    <!-- Headline -->
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <div class="flex items-baseline gap-2">
          <span class="text-3xl font-semibold text-foreground">{{ scorePct ?? '—' }}<span v-if="scorePct !== null" class="text-lg">%</span></span>
          <span class="text-sm text-muted-foreground">{{ scoreLabel }}</span>
        </div>
        <p class="text-xs text-muted-foreground mt-0.5">
          {{ armWords(report.arm) }} · {{ report.samples }} sample(s)
          <span v-if="freshness"> · measured {{ freshness }}</span>
        </p>
      </div>
      <div
        class="rounded-md px-3 py-1.5 text-xs font-medium flex items-center gap-1.5"
        :class="
          report.reliable
            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
            : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
        "
      >
        <component :is="report.reliable ? CheckCircle2 : TriangleAlert" class="h-3.5 w-3.5" />
        {{ report.reliable ? 'Reliable' : 'Not yet reliable' }}
      </div>
    </div>

    <ul v-if="doubts.length" class="text-xs text-amber-700 dark:text-amber-400 space-y-1 pl-4 list-disc">
      <li v-for="doubt in doubts" :key="doubt">{{ doubt }}</li>
    </ul>

    <!-- Correct / abstain / hallucinate -->
    <div v-if="answerable && distributionData" class="space-y-1.5">
      <p class="text-xs font-medium text-foreground">How the answers broke down</p>
      <div class="h-24">
        <Bar :data="distributionData" :options="pctBarOptions()" />
      </div>
      <p v-if="answerable.lmi !== null" class="text-xs text-muted-foreground">
        Misinformation index (hallucinated ÷ hallucinated+correct): {{ pct(answerable.lmi) }} —
        lower is safer.
      </p>
    </div>

    <!-- Per-model breakdown -->
    <div v-if="modelsSorted.length" class="space-y-1.5">
      <p class="text-xs font-medium text-foreground">
        Accuracy by model under test
        <span class="text-muted-foreground font-normal">— never averaged, a spread instead</span>
      </p>
      <div :style="{ height: `${modelsChartHeight}px` }">
        <Bar :data="modelsChartData" :options="pctBarOptions()" />
      </div>
      <ul class="text-xs text-muted-foreground space-y-0.5">
        <li v-for="row in modelsSorted" :key="row.model">
          <span class="text-foreground">{{ row.model }}</span> — {{ pct(row.accuracy) }} accurate,
          {{ pct(row.fabrication) }} fabricated on the control set
          <template v-if="row.context_gain !== null"> · {{ contextGainWords(row.context_gain) }}</template>
        </li>
      </ul>
    </div>

    <!-- Per-generator breakdown -->
    <div v-if="skillsSorted.length" class="space-y-1.5">
      <p class="text-xs font-medium text-foreground">Accuracy by question type</p>
      <div :style="{ height: `${skillsChartHeight}px` }">
        <Bar :data="skillsChartData" :options="pctBarOptions()" />
      </div>
    </div>

    <!-- Control set -->
    <div v-if="control" class="space-y-1">
      <p class="text-xs font-medium text-foreground">The control set (no answer exists)</p>
      <p class="text-xs text-muted-foreground">
        {{ control.samples }} question(s) with nothing to find in the corpus — the honest answer
        is to say so. Invented an answer anyway: {{ pct(control.fabricated) }} of the time.
      </p>
      <p v-if="report.discrimination !== null" class="text-xs text-muted-foreground">
        Tells "no answer exists" apart from "I found it": {{ pct(report.discrimination) }} —
        higher means it is not simply guessing "I don't know" at random.
      </p>
    </div>

    <!-- Trust & methodology -->
    <div class="grid sm:grid-cols-2 gap-4 text-xs">
      <div v-if="report.trust" class="space-y-1">
        <p class="font-medium text-foreground">Grading</p>
        <p class="text-muted-foreground">{{ report.trust.judges }} judge(s)</p>
        <p v-if="report.trust.agreement !== null" class="text-muted-foreground">
          Inter-judge agreement: {{ pct(report.trust.agreement) }}
        </p>
        <p v-if="report.trust.consistency !== null" class="text-muted-foreground">
          Consistency across repeats: {{ pct(report.trust.consistency) }}
        </p>
        <p v-if="report.trust.pending" class="text-muted-foreground">
          {{ report.trust.pending }} answer(s) awaiting a verdict
        </p>
        <p v-if="report.trust.failed" class="text-muted-foreground">
          {{ report.trust.failed }} call(s) failed outright
        </p>
      </div>
      <div v-if="report.dataset || report.instrument" class="space-y-1">
        <p class="font-medium text-foreground">Measured with</p>
        <p v-if="report.dataset" class="text-muted-foreground">
          {{ report.dataset.questions }} active question(s), {{ report.dataset.mode }} set
          <span v-if="report.dataset.window_days"> · freshness window {{ report.dataset.window_days }}d</span>
        </p>
        <p v-if="report.instrument" class="text-muted-foreground">
          {{ report.instrument.subjects }} model(s) under test · judged by
          {{ report.instrument.judge || `${report.instrument.judges} judge(s)` }}
          · profile {{ report.instrument.profile }}
        </p>
      </div>
    </div>
  </div>
</template>
