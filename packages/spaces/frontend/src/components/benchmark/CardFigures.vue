<script setup lang="ts">
/** The six figures of one run, shared by the run list and the run page. */
import { computed } from 'vue'

import StatTile from './StatTile.vue'
import type { BenchmarkCard, BenchmarkReport } from '@/api/types'

const props = defineProps<{ card: BenchmarkCard | BenchmarkReport }>()

const percent = (value: number | null | undefined): string =>
  value == null ? '—' : `${Math.round(value * 100)}%`

const searching = computed(() => props.card.kind === 'retrieval')

/** Retrieval: the hit rate. Answering: accuracy, plus the search hit rate when it differs. */
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
      help="Repeats that gave the same answer; a dash means the block was not run."
    />
    <StatTile
      :value="percent(card.pressure?.flip_rate)"
      label="flipped"
      help="Right answers given up under push-back; a dash means the block was not run."
    />
    <StatTile :value="String(subjects || '—')" label="models" help="Models under test." />
  </div>
</template>
