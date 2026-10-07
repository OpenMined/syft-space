<template>
  <TooltipProvider v-if="hint" :delay-duration="300">
    <Tooltip>
      <TooltipTrigger as-child>
        <span class="text-xs text-muted-foreground whitespace-nowrap" data-testid="utc-stamp-hint">
          {{ hint.label }}
        </span>
      </TooltipTrigger>
      <TooltipContent>{{ hint.title }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { utcStampHintForPath, type UtcStampFormatOptions } from '@/lib/utcStamp'

/** Local-time hint for a path containing a `YYYY-MM-DD_HHMM_UTC` segment; renders nothing otherwise. */
const props = defineProps<{
  path: string
  locale?: UtcStampFormatOptions['locale']
  timeZone?: UtcStampFormatOptions['timeZone']
}>()

const hint = computed(() =>
  utcStampHintForPath(props.path, { locale: props.locale, timeZone: props.timeZone }),
)
</script>
