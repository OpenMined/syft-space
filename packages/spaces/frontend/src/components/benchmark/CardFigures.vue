<script setup lang="ts">
/**
 * The six figures of one run, wherever it is shown.
 *
 * Extracted so the list and the run's own page cannot drift apart: two runs are
 * compared by the figures sitting in the same places, and a figure that means
 * one thing in the list and another on the page it opens would be worse than no
 * figure at all.
 */
import { computed } from 'vue'

import StatTile from './StatTile.vue'
import type { BenchmarkCard, BenchmarkReport } from '@/api/types'

const props = defineProps<{ card: BenchmarkCard | BenchmarkReport }>()

const percent = (value: number | null | undefined): string =>
  value == null ? '—' : `${Math.round(value * 100)}%`

const searching = computed(() => props.card.kind === 'retrieval')

/**
 * The headline tile, and why it sometimes carries two numbers.
 *
 * An endpoint that answers with its own model is two things at once: a search
 * that either finds the material or does not, and a model that either uses it
 * correctly or does not. Split across two tiles those read as unrelated
 * figures; together — 71%/95% — they say plainly that the search is not what is
 * letting this endpoint down. A retrieval endpoint has only the one number, and
 * showing it twice would be noise.
 */
const headline = computed(() => {
  const score = percent(props.card.score)
  const found = props.card.retrieval == null ? null : percent(props.card.retrieval)
  if (searching.value) {
    return {
      value: props.card.score == null ? (found ?? '—') : score,
      label: 'found',
      help: 'Questions where the search found the right material.',
    }
  }
  if (found === null || found === score) {
    return { value: score, label: 'correct', help: 'Answers that matched the reference.' }
  }
  return {
    value: `${score}/${found}`,
    label: 'correct / found',
    help: 'Answer accuracy, then search hit rate.',
  }
})

const subjects = computed(() => props.card.instrument?.subjects ?? props.card.models.length)
</script>

<template>
  <!-- Each in its own box with a little air around it: six separate things
       rather than one long sentence of numbers. -->
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
    <StatTile :value="headline.value" :label="headline.label" :help="headline.help" />
    <StatTile
      :value="percent(card.fabrication_rate)"
      label="invented"
      help="Unanswerable questions answered anyway."
    />
    <StatTile
      :value="String(card.samples ?? '—')"
      label="questions"
      help="Questions graded in this run."
    />
    <StatTile
      :value="percent(card.trust?.consistency)"
      label="repeats"
      help="Repeats that came back with the same answer. Dash — block not run."
    />
    <StatTile
      :value="percent(card.pressure?.flip_rate)"
      label="flipped"
      help="Right answers given up under push-back. Dash — block not run."
    />
    <StatTile :value="String(subjects || '—')" label="models" help="Models under test." />
  </div>
</template>
