<script setup lang="ts">
/** An amber badge with its explanation on hover: a stopped run, a model that failed. */
import { Badge } from '@/components/ui/badge'
import Hint from '../Hint.vue'
import { TONE } from '../labels'

defineOptions({ inheritAttrs: false })

defineProps<{ tip?: string | null }>()
</script>

<template>
  <Hint :text="tip">
    <Badge
      variant="outline"
      :class="TONE.caution"
      class="border-transparent cursor-help"
      v-bind="$attrs"
    >
      <slot />
    </Badge>
  </Hint>
</template>
