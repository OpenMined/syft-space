<script setup lang="ts">
/** A model name chip, the same for every role; the vendor prefix shows on hover. */
import { Badge } from '@/components/ui/badge'
import { shortModel } from './labels'

defineProps<{ name: string }>()
</script>

<template>
  <Badge
    variant="secondary"
    class="font-normal bg-lime-300 text-lime-950 dark:bg-lime-400 dark:text-lime-950"
    :title="name"
  >
    {{ shortModel(name) }}
  </Badge>
</template>
