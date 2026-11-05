<script setup lang="ts">
/** Why a kind stopped writing. */
import { kindStoppedLabel } from '../../filter'
import { TONE } from '../../labels'

defineProps<{ stopped: string }>()

const STOP_TONE: Record<string, string> = {
  'budget reached': TONE.good,
  'failure streak': TONE.bad,
}
</script>

<template>
  <span
    class="rounded px-1.5 py-0.5 text-xs whitespace-nowrap"
    :class="STOP_TONE[stopped] ?? TONE.muted"
    >{{ kindStoppedLabel(stopped) }}</span
  >
</template>
