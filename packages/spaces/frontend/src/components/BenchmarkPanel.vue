<template>
  <div class="space-y-6">
    <!-- Whether anyone is measuring this endpoint, and the button that sets it
         going. Above the card because it is the question that comes first: a
         card is what a run left behind, and without a run there is none. -->
    <RunControl :slug="slug" @finished="load" />

  <div v-if="loading" class="space-y-4">
    <Skeleton class="h-24 w-full" />
    <Skeleton class="h-40 w-full" />
  </div>

  <!-- Nobody measured this endpoint. Not a score of zero — the absence of a
       claim, and it has to read that way. -->
  <div
    v-else-if="!quality?.reported"
    class="border border-border/50 rounded-lg p-8 text-center"
  >
    <FlaskConical class="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
    <h3 class="text-sm font-medium text-foreground mb-1">No benchmark has reported</h3>
    <p class="text-xs text-muted-foreground max-w-md mx-auto">
      Nothing is published about this endpoint's quality. That is not a score of
      zero — it means nobody has measured it yet.
      <span v-if="mode === 'off'">
        Reporting is switched off in Settings, so a benchmark cannot hand results
        to this Space.
      </span>
    </p>
  </div>

  <div v-else class="space-y-6">
    <p class="text-xs text-muted-foreground max-w-2xl">
      Everything below is the <strong class="text-foreground">card</strong> — the benchmark's
      write-up of one run, retained even where it was never sent anywhere. The first section is
      what is currently shown to the outside world (if published); the rest is the same run's own
      detail, for you alone.
      <strong class="text-foreground">A dash (—) means not computed</strong>, never zero — usually
      because the check it comes from was not part of the configured methodology.
    </p>

    <!-- What the outside world sees right now, and how to take it back. The
         owner's question is not "is this good" but "do I vouch for it", so the
         published claim and the way to withdraw it come first. -->
    <section class="border border-border/50 rounded-lg p-5">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="space-y-1">
          <h2 class="heading-3 text-foreground flex items-center gap-2">
            <Megaphone class="h-5 w-5 text-muted-foreground" />
            Published about this endpoint
          </h2>
          <p class="text-xs text-muted-foreground">
            Measured {{ formatDate(quality.checked_at) }}
            <span v-if="publishedWhere"> · showing at {{ publishedWhere }}</span>
            <span v-else> · not published to any marketplace</span>
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="retracting"
          class="text-destructive hover:text-destructive"
          @click="retract"
        >
          <Undo2 class="h-4 w-4 mr-1.5" />
          {{ retracting ? 'Retracting…' : 'Retract' }}
        </Button>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
        <Figure
          :label="searching ? 'found' : 'correct'"
          :value="percent(quality.score)"
          :hint="
            searching
              ? 'the search returned the right material'
              : 'the answer matched the reference'
          "
        />
        <Figure
          label="invented"
          :value="percent(quality.fabrication_rate)"
          hint="answered a question your corpus cannot answer"
        />
        <Figure label="questions" :value="String(quality.samples ?? '—')" hint="graded in this run" />
        <Figure
          label="vouched for"
          :value="quality.reliable ? 'yes' : 'no'"
          hint="whether the benchmark stands behind it"
        />
      </div>

      <p class="text-xs text-muted-foreground mt-4">
        A card carries no expiry. What is above stands at every marketplace until
        a newer one replaces it or you retract it here.
      </p>
    </section>

    <!-- Grounds to doubt. Named before the diagnostics, because if the run
         cannot be trusted then nothing below describes the endpoint. -->
    <section
      v-if="doubts.length"
      class="border border-amber-500/40 bg-amber-500/5 rounded-lg p-5"
    >
      <h2 class="heading-3 text-foreground mb-3 flex items-center gap-2">
        <TriangleAlert class="h-5 w-5 text-amber-500" />
        Grounds to doubt this run
      </h2>
      <ul class="space-y-2">
        <li v-for="doubt in doubts" :key="doubt.code" class="text-sm">
          <span class="text-foreground font-medium">{{ doubt.title }}</span>
          <span class="text-muted-foreground"> — {{ doubt.detail }}</span>
        </li>
      </ul>
      <p class="text-xs text-muted-foreground mt-3">
        These are the benchmark's own reservations. A figure nobody stands behind
        is worse than no figure: a reader sees an absence, but takes a bare number
        at face value.
      </p>
    </section>

    <!-- What you can actually go and fix. -->
    <section v-if="report" class="border border-border/50 rounded-lg p-5">
      <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
        <Wrench class="h-5 w-5 text-muted-foreground" />
        Where it breaks
      </h2>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
        <Figure
          label="search found it"
          :value="percent(report.retrieval)"
          hint="your side of the answer"
        />
        <Figure
          label="risk per answer"
          :value="percent(report.answerable?.lmi)"
          hint="of the times it answered, how often wrong"
        />
        <Figure
          label="silence is a signal"
          :value="signed(report.discrimination)"
          hint="refuses more when there is nothing to find"
        />
        <Figure
          label="answers repeat"
          :value="percent(report.trust?.consistency)"
          hint="same question, same answer"
        />
      </div>

      <div v-if="report.skills.length" class="space-y-2">
        <h3 class="text-xs font-medium text-foreground">By type of question</h3>
        <ul class="space-y-1.5">
          <li
            v-for="skill in report.skills"
            :key="skill.generator"
            class="flex items-center gap-3 text-xs"
          >
            <span class="text-muted-foreground w-44 truncate">{{ skill.generator }}</span>
            <div class="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                class="h-full"
                :class="skill.accuracy < 0.6 ? 'bg-destructive/70' : 'bg-primary/60'"
                :style="{ width: `${Math.round(skill.accuracy * 100)}%` }"
              />
            </div>
            <span class="text-foreground font-medium w-10 text-right">
              {{ percent(skill.accuracy) }}
            </span>
            <span class="text-muted-foreground w-16 text-right">{{ skill.samples }} q</span>
          </li>
        </ul>
        <p class="text-xs text-muted-foreground pt-1">
          One share over every type of question hides exactly what needs fixing.
        </p>
      </div>
    </section>

    <!-- Whose result it is. The owner is entitled to know which model his
         endpoint falls apart with — the public page only shows the spread. -->
    <section v-if="report?.models.length" class="border border-border/50 rounded-lg p-5">
      <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
        <Boxes class="h-5 w-5 text-muted-foreground" />
        With each model the benchmark tried
      </h2>
      <ul class="space-y-1.5">
        <li
          v-for="row in report.models"
          :key="row.model"
          class="flex items-center gap-3 text-xs"
        >
          <span class="text-muted-foreground w-52 truncate" :title="row.model">
            {{ row.model }}
          </span>
          <div class="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              class="h-full bg-primary/60"
              :style="{ width: `${Math.round(row.accuracy * 100)}%` }"
            />
          </div>
          <span class="text-foreground font-medium w-10 text-right">
            {{ percent(row.accuracy) }}
          </span>
          <span
            v-if="row.context_gain != null"
            class="w-12 text-right"
            :class="row.context_gain > 0 ? 'text-destructive' : 'text-muted-foreground'"
            title="What your material did to that model's honesty. Positive means your context made it bolder, not better."
          >
            {{ signed(row.context_gain) }}
          </span>
        </li>
      </ul>
      <p class="text-xs text-muted-foreground mt-3">
        The last column is what your material did to that model's honesty. A plus
        means your context made it bolder rather than better — that one is yours,
        not the model's.
      </p>
    </section>

    <!-- What was measured, and with what. Two runs over different windows of a
         growing corpus are not the same measurement, and the share alone never
         says so. -->
    <section v-if="report" class="border border-border/50 rounded-lg p-5">
      <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
        <Ruler class="h-5 w-5 text-muted-foreground" />
        What was measured, and with what
      </h2>
      <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-xs">
        <Row label="Kind" :value="searching ? 'retrieval (your search)' : 'answering (your answer)'" />
        <Row label="Questions" :value="`${report.samples} graded`" />
        <Row
          label="Built from"
          :value="
            report.dataset
              ? report.dataset.window_days > 0
                ? `the last ${report.dataset.window_days} days of the corpus`
                : 'the whole corpus'
              : '—'
          "
        />
        <Row label="Question pool" :value="report.dataset?.cohort || '—'" />
        <Row label="Graded by" :value="report.instrument?.judge || '—'" />
        <Row
          label="Graders"
          :value="
            report.trust
              ? `${report.trust.judges}` +
                (report.trust.agreement != null
                  ? `, agreeing ${percent(report.trust.agreement)} of the time`
                  : '')
              : '—'
          "
        />
        <Row label="Methodology profile" :value="report.instrument?.profile || '—'" />
        <Row label="Models tried" :value="String(report.instrument?.subjects ?? report.models.length)" />
      </dl>
      <p class="text-xs text-muted-foreground mt-4">
        Same material, a different pool of questions, and metrics that move a long
        way — that is a reason to suspect the questions rather than this endpoint.
      </p>
    </section>
  </div>
  </div>
</template>

<script setup lang="ts">
/**
 * The benchmark card, as its owner reads it.
 *
 * The marketplace page answers "should I use this endpoint". This one answers
 * a different question, and the difference decides everything on it: **do I
 * vouch for what is being said in my name, and if not, how do I take it back?**
 *
 * So the published claim and the Retract button come first, the benchmark's own
 * reservations second, and only then the diagnostics — because if the run
 * cannot be trusted, nothing below it describes the endpoint at all.
 */
import { computed, onMounted, ref, watch, h } from 'vue'
import { toast } from 'vue-sonner'
import {
  Boxes,
  FlaskConical,
  Megaphone,
  Ruler,
  TriangleAlert,
  Undo2,
  Wrench,
} from 'lucide-vue-next'

import RunControl from '@/components/benchmark/RunControl.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { settingsApi } from '@/api/endpoints/settings'
import type { BenchmarksMode, EndpointQualityResponse } from '@/api/types'

const props = defineProps<{ slug: string }>()

const loading = ref(true)
const retracting = ref(false)
const quality = ref<EndpointQualityResponse | null>(null)
const mode = ref<BenchmarksMode>('off')

const report = computed(() => quality.value?.report ?? null)
const searching = computed(() => quality.value?.kind === 'retrieval')

const publishedWhere = computed(() => {
  const where = quality.value?.published_to ?? []
  if (where.length === 0) return ''
  return where.length === 1 ? '1 marketplace' : `${where.length} marketplaces`
})

/**
 * The benchmark sends codes; the words are ours.
 *
 * Each one is a reason the owner might not want this published, phrased as what
 * it means for him rather than as what the benchmark measured.
 */
const DOUBTS: Record<string, { title: string; detail: string }> = {
  few_samples: {
    title: 'Too few questions',
    detail:
      'the shares move by whole points on a single verdict, so they say more about which questions were asked than about the endpoint',
  },
  judges_disagree: {
    title: 'The graders disagreed',
    detail:
      'they differ from each other by more than endpoints usually differ, so a comparison against another endpoint means little',
  },
  uneven_coverage: {
    title: 'Some question types were barely measured',
    detail:
      'usually an interrupted run; the shares are computed over a skewed sample and look exactly like ordinary shares',
  },
  pending_verdicts: {
    title: 'Part of the run was never graded',
    detail: 'answers were collected but no verdict was recorded for them',
  },
  failed_calls: {
    title: 'Some calls failed',
    detail: 'that much of the measurement did not happen at all',
  },
}

const doubts = computed(() => {
  const flags = report.value?.trust?.flags ?? []
  return flags.map((code) => ({
    code,
    title: DOUBTS[code]?.title ?? code,
    detail: DOUBTS[code]?.detail ?? 'reported by the benchmark',
  }))
})

function percent(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${Math.round(value * 100)}%`
}

function signed(value: number | null | undefined): string {
  if (value == null) return '—'
  const rounded = Math.round(value * 100)
  return `${rounded > 0 ? '+' : ''}${rounded}%`
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/** A figure with its name and what it means, so no number stands bare. */
const Figure = (props: { label: string; value: string; hint: string }) =>
  h('div', { class: 'space-y-0.5' }, [
    h('div', { class: 'text-lg font-semibold text-foreground' }, props.value),
    h('div', { class: 'text-xs font-medium text-foreground' }, props.label),
    h('div', { class: 'text-xs text-muted-foreground' }, props.hint),
  ])

const Row = (props: { label: string; value: string }) =>
  h('div', { class: 'flex justify-between gap-4 border-b border-border/30 py-1' }, [
    h('dt', { class: 'text-muted-foreground' }, props.label),
    h('dd', { class: 'text-foreground text-right' }, props.value),
  ])

async function load() {
  loading.value = true
  try {
    const [card, benchmarks] = await Promise.all([
      endpointsApi.getQuality(props.slug),
      settingsApi.getBenchmarksMode().catch(() => ({ mode: 'off' as BenchmarksMode })),
    ])
    quality.value = card
    mode.value = benchmarks.mode
  } catch {
    quality.value = null
  } finally {
    loading.value = false
  }
}

async function retract() {
  retracting.value = true
  try {
    const result = await endpointsApi.retractQuality(props.slug)
    const refused = result.results.filter((r) => !r.success && r.supported)
    if (!result.cleared) {
      toast.info('There was nothing published to take down')
    } else if (refused.length) {
      // Said plainly rather than swallowed: the local copy is gone but the
      // claim is still out there, and only the owner can chase it.
      toast.warning(
        `Withdrawn here, but ${refused.length} marketplace(s) refused — the card may still be showing there`,
      )
    } else {
      toast.success('Withdrawn here and at every marketplace showing it')
    }
    await load()
  } catch {
    toast.error('Could not withdraw the card')
  } finally {
    retracting.value = false
  }
}

onMounted(load)
watch(() => props.slug, load)
</script>
