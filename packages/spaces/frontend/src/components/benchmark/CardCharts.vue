<script setup lang="ts">
/**
 * One run, drawn: three tiles, side by side, and not a line of prose between
 * them.
 *
 * A single headline share hides exactly what the owner can go and fix — the
 * model that invents on half the questions, the one type of question the
 * endpoint fails at — so the breakdowns are drawn rather than listed. What each
 * chart means sits behind the mark in its corner: three charts with a paragraph
 * under each is a page nobody reads to the bottom.
 *
 * Every axis runs the full 0-100 (see `charts.ts`), so no run can look better
 * by being drawn on its own. The three plots are given one height — the tallest
 * one's — and sit at the bottom of their tiles: three charts of three different
 * heights invite the eye to compare their sizes, which mean nothing.
 *
 * The props are structural on purpose: a published card and the console's own
 * build carry the same figures under the same names, and this draws either.
 */
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
import { generatorWords } from './labels'

ChartJS.register(CategoryScale, LinearScale, BarElement, ChartTooltip, Legend)

interface ShareRow {
  correct: number
  abstain: number
  hallucinate: number
}

interface ModelRow {
  model: string
  samples?: number
  accuracy: number
  /** The same model with nothing in front of it — absent where arm A was not run. */
  closed_accuracy?: number | null
}

interface PressureRow {
  /** Share still standing after each round of push-back, first round first. */
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
  /** The denial loop's shape; absent where the block was not run. */
  pressure?: PressureRow | null
  /** The monte carlo block's shape; absent where it was not run. */
  stability?: StabilityRow | null
}>()

const distribution = computed(() => {
  const share = props.answerable
  if (!share) return null
  return {
    labels: ['Correct', 'Abstained', 'Invented'],
    datasets: [
      {
        data: [
          Math.round(share.correct * 100),
          Math.round(share.abstain * 100),
          Math.round(share.hallucinate * 100),
        ],
        backgroundColor: [CHART_COLORS.correct, CHART_COLORS.abstain, CHART_COLORS.hallucinate],
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

/**
 * Only the generators this run actually answered questions from.
 *
 * A generator switched off before the run has nothing in it, and a bar at zero
 * would read as "this endpoint fails at that kind of question" — a claim
 * nobody measured. A generator that was asked and got everything wrong is the
 * opposite case: its zero is the finding, and it stays.
 */
const skills = computed(() =>
  [...props.skills].filter((row) => row.samples > 0).sort((a, b) => b.accuracy - a.accuracy),
)
const skillsChart = computed(() => ({
  labels: skills.value.map((row) => generatorWords(row.generator).label),
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

/**
 * How many of the answers that were pushed back on were still standing after
 * each round.
 *
 * The flip rate says how many gave in; this says when. An endpoint that folds
 * at the first word of disagreement and one that holds out to the last round
 * can report the same rate, and they are not the same product to put in front
 * of a user who argues.
 */
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

/** Accuracy at each temperature the repeats were asked at — where it wanders. */
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

/**
 * The one comparison the arms exist for: the same model with nothing in front
 * of it, and with this endpoint's material.
 *
 * Only the models that were asked both ways can say anything here, so a model
 * measured in one arm alone is left out rather than drawn against a zero.
 */
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

/**
 * One height for all of them: the tallest plot's, so none of them scrolls.
 *
 * With the height fixed, a chart of one bar would otherwise draw it as a slab
 * half the tile deep — which reads as emphasis and means nothing. The bars are
 * capped (`maxBarThickness`) and settle at the foot of the tile instead.
 */
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

  <!-- Each tile is a column with the plot pushed to its foot, so the three
       baselines line up however long the titles run. -->
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
        <InfoTip text="Accuracy per model. Never averaged." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="modelsChart" :options="pctBarOptions()" />
      </div>
    </div>

    <div v-if="skills.length" class="border border-border/60 rounded-lg p-3 flex flex-col">
      <div class="flex items-center gap-1.5 mb-2">
        <h4 class="text-xs font-medium text-foreground">By type of question</h4>
        <InfoTip text="Accuracy per generator. Only the ones this run asked." />
      </div>
      <div class="mt-auto" :style="{ height: `${plotHeight}px` }">
        <Bar :data="skillsChart" :options="pctBarOptions()" />
      </div>
    </div>

    <!-- The two blocks that cost several times the direct test, and the one
         comparison the arms exist for. Each is absent rather than empty where
         its block was not run: a bar at zero would be a claim nobody measured. -->
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
