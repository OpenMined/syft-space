<script setup lang="ts">
/** A verdict in words, coloured by verdict; control kinds show the fine outcome. */
import { cn } from '@/lib/utils'
import Hint from '../../Hint.vue'
import { DASH } from '../figures'
import { outcomeLabel, verdictColors, verdictTip } from '../labels'

// Attributes such as a test id go on the pill, not on the tooltip around it.
defineOptions({ inheritAttrs: false })

withDefaults(
  defineProps<{
    verdict: string | null
    generator?: string | null
    behavior?: string | null
    /** False inside a control, such as a row's toggle button. */
    focusable?: boolean
  }>(),
  { generator: null, behavior: null, focusable: true },
)
</script>

<template>
  <Hint v-if="verdict" :text="verdictTip(verdict)" :focusable="focusable">
    <span
      :class="
        cn(
          'inline-block rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap',
          verdictColors(verdict),
        )
      "
      :data-verdict="verdict"
      v-bind="$attrs"
      >{{ outcomeLabel(generator, verdict, behavior) }}</span
    >
  </Hint>
  <span v-else class="text-muted-foreground" v-bind="$attrs">{{ DASH }}</span>
</template>
