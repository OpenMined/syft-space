<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import { Loader2 } from 'lucide-vue-next'
import type { SpaceHealth } from '@/lib/types'

defineProps<{ health: SpaceHealth }>()

const config: Record<SpaceHealth, { label: string; classes: string; dot: string }> = {
  healthy: {
    label: 'Running',
    classes: 'bg-success/15 text-foreground border-success/40',
    dot: 'bg-success',
  },
  unhealthy: {
    label: 'Needs attention',
    classes: 'bg-destructive/10 text-destructive border-destructive/40',
    dot: 'bg-destructive',
  },
  restarting: {
    label: 'Restarting',
    classes: 'bg-warning/15 text-foreground border-warning/40',
    dot: '',
  },
  starting: {
    label: 'Starting',
    classes: 'bg-warning/15 text-foreground border-warning/40',
    dot: '',
  },
  paused: {
    label: 'Paused',
    classes: 'bg-muted text-muted-foreground border-transparent',
    dot: 'bg-muted-foreground',
  },
}
</script>

<template>
  <Badge variant="outline" :class="['gap-1.5 font-normal', config[health].classes]">
    <Loader2 v-if="health === 'restarting' || health === 'starting'" class="h-3 w-3 animate-spin" />
    <span v-else :class="['h-2 w-2 rounded-full', config[health].dot]" />
    {{ config[health].label }}
  </Badge>
</template>
