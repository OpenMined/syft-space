<script setup lang="ts">
/** One run's breakdown charts; draws a stored card or a live build. */
import { computed } from 'vue'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip as ChartTooltip,
} from 'chart.js'
import { Bar } from 'vue-chartjs'

import InfoTip from './InfoTip.vue'
import { barChartHeight, CHART_COLORS, pctBarOptions } from './charts'
import { generatorWords, guessText } from './labels'

ChartJS.register(CategoryScale, LinearScale, BarElement, ChartTooltip, Legend)

interface ShareRow {
  correct: number
  abstain: number
  hallucinate: number
  /** Optional. */
  incomplete?: number | null
}

interface ModelRow {
  model: string
  samples?: number
  accuracy: number
  /** The same model without data; absent when arm A did not run. */
  closed_accuracy?: number | null
}

interface PressureRow {
  /** Share still right after each round of push-back. */
  held?: number[]
}

interface TemperatureRow {
  temperature: number
  accuracy: number
}

interface StabilityRow {
  by_temperature?: TemperatureRow[]
}

interface SkillRow {
  generator: string
  samples: number
  accuracy: number
}

const props = defineProps<{
  answerable?: ShareRow | null
  models: ModelRow[]
  skills: SkillRow[]
  /** Denial loop results; absent when the block did not run. */
  pressure?: PressureRow | null
  /** Monte carlo results; absent when the block did not run. */
  stability?: StabilityRow | null
}>()

const distribution = computed(() => {
  const share = props.answerable
  if (!share) return null
  const bars: { label: string; value: number; color: string }[] = [
    { label: 'Correct', value: share.correct, color: CHART_COLORS.correct },
    { label: 'Abstained', value: share.abstain, color: CHART_COLORS.abstain },
    { label: 'Invented', value: share.hallucinate, color: CHART_COLORS.hallucinate },
  ]
  if (share.incomplete) {
    bars.push({ label: 'Incomplete', value: share.incomplete, color: CHART_COLORS.incomplete })
  }
  return {
    labels: bars.map((b) => b.label),
    datasets: [
      {
        data: bars.map((b) => Math.round(b.value * 100)),
        backgroundColor: bars.map((b) => b.color),
        borderRadius: 6,
        barPercentage: 0.6,
        maxBarThickness: 26,
      },
    ],
  }
})

const models = computed(() => [...props.models].sort((a, b) => b.accuracy - a.accuracy))
const modelsChart = computed(() => ({
  labels: models.value.map((row) => row.model),
  datasets: [
    {
      data: models.value.map((row) => Math.round(row.accuracy * 100)),
      backgroundColor: CHART_COLORS.model,
      borderRadius: 6,
      barPercentage: 0.6,
      maxBarThickness: 26,
    },
  ],
}))

/** Only generators with questions in this run; a measured zero stays. */
const skills = computed(() =>
  [...props.skills].filter((row) => row.samples > 0).sort((a, b) => b.accuracy - a.accuracy),
)
const skillsChart = computed(() => ({
  labels: skills.value.map((row) => {
    const label = generatorWords(row.generator).label
    const guess = guessText(row.generator)
    return guess ? `${label} · ${guess}` : label
  }),
  datasets: [
    {
      data: skills.value.map((row) => Math.round(row.accuracy * 100)),
      backgroundColor: CHART_COLORS.skill,
      borderRadius: 6,
      barPercentage: 0.6,
      maxBarThickness: 26,
    },
  ],
}))

/** Share of pushed-back answers still right after each round. */
const held = computed(() => props.pressure?.held ?? [])
const heldChart = computed(() => ({
  labels: held.value.map((_, index) => `round ${index + 1}`),
  datasets: [
    {
      data: held.value.map((share) => Math.round(share * 100)),
      backgroundColor: CHART_COLORS.held,
      borderRadius: 6,
      barPercentage: 0.6,
      maxBarThickness: 26,
    },
  ],
}))

/** Accuracy at each repeat temperature. */
const temperatures = computed(() =>
  [...(props.stability?.by_temperature ?? [])].sort((a, b) => a.temperature - b.temperature),
)
const temperatureChart = computed(() => ({
  labels: temperatures.value.map((row) => `t ${row.temperature}`),
  datasets: [
    {
      data: temperatures.value.map((row) => Math.round(row.accuracy * 100)),
      backgroundColor: CHART_COLORS.temperature,
      borderRadius: 6,
      barPercentage: 0.6,
      maxBarThickness: 26,
    },
  ],
}))

/** Models asked both without and with data. */
const contrasted = computed(() => models.value.filter((row) => row.closed_accuracy != null))
const contextChart = computed(() => ({
  labels: contrasted.value.map((row) => row.model),
  datasets: [
    {
      label: 'on its own',
      data: contrasted.value.map((row) => Math.round((row.closed_accuracy ?? 0) * 100)),
      backgroundColor: CHART_COLORS.alone,
      borderRadius: 6,
      barPercentage: 0.7,
      maxBarThickness: 18,
    },
    {
      label: 'with your material',
      data: contrasted.value.map((row) => Math.round(row.accuracy * 100)),
      backgroundColor: CHART_COLORS.model,
      borderRadius: 6,
      barPercentage: 0.7,
      maxBarThickness: 18,
    },
  ],
}))

/** One plot height for all tiles: the tallest plot's. */
const plotHeight = computed(() =>
  barChartHeight(
    Math.max(
      distribution.value ? 3 : 0,
      models.value.length,
      skills.value.length,
      held.value.length,
      temperatures.value.length,
      // Two bars per model, and they need the room of two rows.
      contrasted.value.length * 2,
    ),
  ),
)

const nothingToDraw = computed(
  () =>
    !distribution.value &&
    !models.value.length &&
    !skills.value.length &&
    !held.value.length &&
    !temperatures.value.length,
)
</script>

<template>
  <div v-if="nothingToDraw" class="text-xs text-muted-foreground">
    Nothing to break down in this run.
  </div>

  <div v-else class="grid gap-3 md:grid-cols-3">
    <div v-if="distribution" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">Answer breakdown</h4>
        <InfoTip text="The answerable half: right, refused, invented." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="distribution" :options="pctBarOptions()" />
      </div>
    </div>

    <div v-if="models.length" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">By model under test</h4>
        <InfoTip text="Accuracy per model, never averaged." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="modelsChart" :options="pctBarOptions()" />
      </div>
    </div>

    <div v-if="skills.length" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">By type of question</h4>
        <InfoTip
          text="Accuracy per question type in this run; guess is what picking at random would score."
        />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="skillsChart" :options="pctBarOptions()" />
      </div>
    </div>

    <div v-if="held.length" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">Held under pressure</h4>
        <InfoTip text="Right answers still standing after each round of push-back." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="heldChart" :options="pctBarOptions()" />
      </div>
    </div>

    <div v-if="temperatures.length" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">Accuracy by temperature</h4>
        <InfoTip text="Accuracy at each temperature the repeats were asked at." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="temperatureChart" :options="pctBarOptions()" />
      </div>
    </div>

    <div v-if="contrasted.length" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">With and without your material</h4>
        <InfoTip text="The same model alone, then with your material." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="contextChart" :options="pctBarOptions(true)" />
      </div>
    </div>
  </div>
</template>
