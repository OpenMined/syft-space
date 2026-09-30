<script setup lang="ts">
/**
 * One figure, one word for it, and the explanation on demand.
 *
 * The word under the number is deliberately a single one: six tiles in a row
 * are read at a glance, and a sentence under each turns the row into a wall of
 * prose nobody reads. What the figure actually means sits behind the mark at
 * the corner — available to whoever wants it, invisible to whoever does not.
 *
 * A dash is what "not computed" looks like, and it never rounds to zero: a
 * block that was not run and a block that found nothing are different facts.
 */
import InfoTip from './InfoTip.vue'

defineProps<{
  /** Already formatted — the tile does no arithmetic and no rounding. */
  value: string
  /** One word, lower case. */
  label: string
  /** What it means, in one line. */
  help: string
}>()
</script>

<template>
  <div class="relative p-3 sm:p-4 border border-border/60 rounded-md">
    <div class="absolute top-2 right-2">
      <InfoTip :text="help" />
    </div>
    <div class="text-xl font-semibold text-foreground tabular-nums pr-5">{{ value }}</div>
    <div class="text-xs text-muted-foreground mt-0.5">{{ label }}</div>
  </div>
</template>
