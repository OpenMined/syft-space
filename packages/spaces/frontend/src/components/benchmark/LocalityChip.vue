<script setup lang="ts">
/** Whether an address stays on this machine, with the host in a tooltip. */
import { ArrowUpRight, HardDrive } from 'lucide-vue-next'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

defineProps<{
  local: boolean
  /** One sentence naming the host. */
  tip: string
}>()
</script>

<template>
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger as-child>
        <span
          class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md cursor-default"
          :class="
            local
              ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
              : 'bg-sky-500/10 text-sky-700 dark:text-sky-400'
          "
          data-testid="locality"
        >
          <component :is="local ? HardDrive : ArrowUpRight" class="h-3 w-3" />
          {{ local ? 'Stays local' : 'Leaves machine' }}
        </span>
      </TooltipTrigger>
      <TooltipContent class="max-w-64">{{ tip }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
