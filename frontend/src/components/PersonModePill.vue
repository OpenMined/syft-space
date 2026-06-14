<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import type { ReplyMode } from '@/stores/mockRelationships'

defineProps<{ mode: ReplyMode }>()
</script>

<template>
  <Badge
    variant="outline"
    class="text-[11px] px-2 py-0.5"
    :class="
      mode === 'auto'
        ? 'bg-green-500/10 text-green-600 border-green-500/20'
        : 'bg-amber-500/10 text-amber-600 border-amber-500/20'
    "
  >
    {{ mode === 'auto' ? 'Auto' : 'Manual' }}
  </Badge>
</template>
