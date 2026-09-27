<script setup lang="ts">
/**
 * The console's outer layout: "Preparation" and "Testing", each collapsing
 * a couple of phase blocks — progressive disclosure over five equal blocks
 * shown flat.
 */
import { ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

defineProps<{
  title: string
  status: string
  actionLabel: string
  actionDisabled?: boolean
  actionTitle?: string
  /** Styled as a stop rather than a start — the run button turns into this
   * while a job it started is queued or running. */
  actionDestructive?: boolean
  open?: boolean
}>()
const emit = defineEmits<{ action: []; 'update:open': [boolean] }>()
</script>

<template>
  <details
    class="group/outer border border-border rounded-lg"
    :open="open ?? false"
    @toggle="emit('update:open', ($event.target as HTMLDetailsElement).open)"
  >
    <summary
      class="flex items-center gap-3 p-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden"
    >
      <ChevronRight class="h-4 w-4 transition-transform group-open/outer:rotate-90 shrink-0" />
      <span class="font-semibold text-foreground">{{ title }}</span>
      <span class="text-sm text-muted-foreground truncate">{{ status }}</span>
      <Button
        :variant="actionDestructive ? 'destructive' : 'default'"
        size="sm"
        class="ml-auto shrink-0"
        :disabled="actionDisabled"
        :title="actionTitle"
        @click.stop.prevent="emit('action')"
      >
        {{ actionLabel }}
      </Button>
    </summary>
    <div class="border-t border-border p-4 space-y-4">
      <slot />
    </div>
  </details>
</template>
