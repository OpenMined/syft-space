<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import { Loader2 } from 'lucide-vue-next'
import type { RequestStatus } from '@/lib/types'

defineProps<{ status: RequestStatus }>()

const config: Record<RequestStatus, { label: string; classes: string; dot: string }> = {
  pending: {
    label: 'Pending review',
    classes: 'bg-secondary text-secondary-foreground border-transparent',
    dot: 'bg-muted-foreground',
  },
  provisioning: {
    label: 'Setting up',
    classes: 'bg-warning/15 text-foreground border-warning/40',
    dot: '',
  },
  active: {
    label: 'Active',
    classes: 'bg-success/15 text-foreground border-success/40',
    dot: 'bg-success',
  },
  rejected: {
    label: 'Rejected',
    classes: 'bg-muted text-muted-foreground border-transparent',
    dot: 'bg-muted-foreground',
  },
  failed: {
    label: 'Failed',
    classes: 'bg-destructive/10 text-destructive border-destructive/40',
    dot: 'bg-destructive',
  },
  deleted: {
    label: 'Deleted',
    classes: 'bg-muted text-muted-foreground border-transparent',
    dot: 'bg-muted-foreground',
  },
}
</script>

<template>
  <Badge variant="outline" :class="['gap-1.5 font-normal', config[status].classes]">
    <Loader2 v-if="status === 'provisioning'" class="h-3 w-3 animate-spin" />
    <span v-else :class="['h-2 w-2 rounded-full', config[status].dot]" />
    {{ config[status].label }}
  </Badge>
</template>
