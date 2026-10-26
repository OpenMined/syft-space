<script setup lang="ts">
/** One figure with a one-word label and a tooltip; a dash means not computed. */
import InfoTip from './InfoTip.vue'

defineProps<{
  /** Already formatted. */
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
