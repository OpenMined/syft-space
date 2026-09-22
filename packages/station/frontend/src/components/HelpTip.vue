<script setup lang="ts">
/**
 * Definition for the thing it sits next to — a column header or a field
 * label, never a whole section. Anything a reader needs in order to make
 * sense of the screen stays visible instead.
 */
import { Info } from 'lucide-vue-next'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
</script>

<template>
  <TooltipProvider :delay-duration="0">
    <Tooltip>
      <TooltipTrigger as-child>
        <Info class="inline h-3 w-3 cursor-help align-[-1px] text-muted-foreground" />
      </TooltipTrigger>
      <TooltipContent class="max-w-xs text-xs font-normal">
        <slot />
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
