<script setup lang="ts">
/** One short line of explanation, on demand rather than printed in full. */
import { Info } from 'lucide-vue-next'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

defineProps<{ text: string }>()
</script>

<template>
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger as-child>
        <button type="button" class="text-muted-foreground hover:text-foreground" :aria-label="text">
          <Info class="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent class="max-w-64">{{ text }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
