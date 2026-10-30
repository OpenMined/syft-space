<script setup lang="ts">
/** Whether an address stays on this machine, with the host in a tooltip. */
import { ArrowUpRight, HardDrive } from 'lucide-vue-next'
import Hint from './Hint.vue'
import { TONE } from './labels'

defineProps<{
  local: boolean
  /** One sentence naming the host. */
  tip: string
}>()
</script>

<template>
  <Hint :text="tip">
    <span
      class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md cursor-default"
      :class="local ? TONE.good : TONE.info"
      data-testid="locality"
    >
      <component :is="local ? HardDrive : ArrowUpRight" class="h-3 w-3" />
      {{ local ? 'Stays local' : 'Leaves machine' }}
    </span>
  </Hint>
</template>
