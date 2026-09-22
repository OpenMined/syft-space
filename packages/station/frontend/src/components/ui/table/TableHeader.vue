<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: HTMLAttributes['class'] }>()
</script>

<template>
  <thead
    data-slot="table-header"
    :class="cn('sticky top-0 z-10 bg-muted/60 [&_tr]:border-b', props.class)"
  >
    <slot />
  </thead>
</template>
