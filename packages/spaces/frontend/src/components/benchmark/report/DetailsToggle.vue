<template>
  <Hint text="Show the prompts, replies and verdicts behind the figures." :focusable="false">
    <label class="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
      <Checkbox v-model="details" data-testid="details-toggle" />
      Details
    </label>
  </Hint>
</template>

<script setup lang="ts">
import { Checkbox } from '@/components/ui/checkbox'
import Hint from '../Hint.vue'
import { useDetails } from './details/useDetails'

const details = useDetails()
</script>
