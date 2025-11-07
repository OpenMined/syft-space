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
    'bg-yellow-50 dark:bg-yellow-950/50 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800',
  success: '', // Will use shadcn variant styling
  pending:
    'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800',
  published: '', // Will use shadcn variant styling
  draft: '', // Will use shadcn variant styling
}

const indicatorClasses = {
  running: 'bg-green-500 dark:bg-green-400',
  stopped: 'bg-muted-foreground',
  error: 'bg-destructive',
  warning: 'bg-yellow-500 dark:bg-yellow-400',
  success: 'bg-green-500 dark:bg-green-400',
  pending: 'bg-blue-500 dark:bg-blue-400',
  published: 'bg-green-500 dark:bg-green-400 animate-pulse',
  draft: 'bg-muted-foreground',
}
</script>
