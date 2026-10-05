<template>
  <section v-if="result" class="space-y-3" data-testid="report-checks">
    <div>
      <div class="flex items-center gap-1.5">
        <h2 class="heading-4">Reliability checks</h2>
        <InfoTip v-if="agreementTip" :text="agreementTip" />
      </div>
      <p class="text-sm text-muted-foreground">
        Extra tests on {{ name }} with your data, so a lab can’t wave the numbers away.
      </p>
    </div>
    <div class="grid grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-2 lg:grid-cols-4">
      <div
        v-for="tile in tiles"
        :key="tile.key"
        class="rounded-lg border bg-card p-4"
        :data-testid="`check-${tile.key}`"
      >
        <p class="text-2xl font-semibold tabular-nums" data-testid="check-value">
          {{ tile.value }}
        </p>
        <div class="mt-2 flex items-start gap-1.5">
          <p class="text-sm font-medium">{{ tile.label }}</p>
          <span v-if="tile.tip" class="mt-0.5 flex"><InfoTip :text="tile.tip" /></span>
        </div>
        <p class="mt-1 text-xs text-muted-foreground">{{ tile.sub }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import InfoTip from '../InfoTip.vue'
import { useRun } from './context'
import { pct } from './figures'
import { modelName } from './labels'

defineProps<{ slug: string; jobId: string; modelId: string | null }>()

const run = useRun()

const result = computed(() => run.modelReport.value?.checks ?? null)

const name = computed(() => (run.model.value ? modelName(run.model.value) : ''))

const agreementTip = computed(() => {
  const agreement = result.value?.agreement ?? null
  return agreement === null ? null : `Judges agreed on ${pct(agreement)} of answers.`
})

const tiles = computed(() => {
  const c = result.value
  if (!c) return []
  const rounds = c.held_by_round ?? []
  const temps = [...(c.by_temperature ?? [])].sort((a, b) => a.t - b.t)
  const steady = temps[0]?.accuracy ?? null
  const looser = temps.length > 1 ? temps[temps.length - 1]!.accuracy : null
  let repeatTip: string | null = null
  if (steady !== null) {
    repeatTip =
      looser === null
        ? `Right ${pct(steady)} of the time when asked again.`
        : `Right ${pct(steady)} of the time at the steady setting, ${pct(looser)} at the looser one.`
  }
  return [
    {
      key: 'challenged',
      value: pct(c.challenged ? c.kept_right : null),
      label: 'Kept a right answer when challenged',
      sub: c.denial_limit
        ? `Told “Are you sure?” up to ${c.denial_limit} times`
        : 'Told “Are you sure?”',
      tip: rounds.length ? `Still right after each round: ${rounds.map(pct).join(', ')}.` : null,
    },
    {
      key: 'repeated',
      value: pct(c.repeated ? c.same_answer : null),
      label: 'Gave the same answer when asked again',
      sub: 'Each question repeated at two settings',
      tip: repeatTip,
    },
    {
      key: 'trick',
      value: c.trick_asked ? `${c.trick_answered} of ${c.trick_asked}` : '—',
      label: 'Trick questions answered anyway',
      sub: 'Questions your reporting has no answer to',
      tip:
        c.trick_alone_asked && c.trick_alone_answered !== null
          ? `On its own it answered ${c.trick_alone_answered} of ${c.trick_alone_asked}.`
          : null,
    },
    {
      key: 'search',
      value: pct(c.searched ? c.search_found : null),
      label: 'Search found the right passage',
      sub: 'Same for every model: it’s your archive’s search',
      tip: c.searched
        ? `It missed the right passage on ${c.missed} of ${c.searched} questions.`
        : null,
    },
  ]
})
</script>
