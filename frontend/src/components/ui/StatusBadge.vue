<template>
  <Badge :variant="variant" :class="['flex items-center gap-1.5', statusClasses[status]]">
    <div :class="['w-2 h-2 rounded-full', indicatorClasses[status]]" />
    {{ label || status }}
  </Badge>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'

export type Status =
  | 'running'
  | 'stopped'
  | 'error'
  | 'warning'
  | 'success'
  | 'pending'
  | 'published'
  | 'draft'

const props = defineProps<{
  status: Status
  label?: string
  variant?: 'default' | 'secondary' | 'destructive' | 'outline'
}>()

const variant = computed(() => {
  if (props.variant) return props.variant

  switch (props.status) {
    case 'error':
      return 'destructive'
    case 'running':
    case 'published':
    case 'success':
      return 'default'
    default:
      return 'outline'
  }
})

const statusClasses = {
  running: '', // Will use shadcn variant styling
  stopped: '', // Will use shadcn variant styling
  error: '', // Will use shadcn variant styling
  warning:
    'bg-accent/10 text-accent-foreground border-accent/50',
  success: '', // Will use shadcn variant styling
  pending:
    'bg-secondary/10 text-secondary-foreground border-secondary/50',
  published: '', // Will use shadcn variant styling
  draft: '', // Will use shadcn variant styling
}

const indicatorClasses = {
  running: 'bg-primary',
  stopped: 'bg-muted-foreground',
  error: 'bg-destructive',
  warning: 'bg-accent',
  success: 'bg-primary',
  pending: 'bg-secondary',
  published: 'bg-primary animate-pulse',
  draft: 'bg-muted-foreground',
}
</script>
