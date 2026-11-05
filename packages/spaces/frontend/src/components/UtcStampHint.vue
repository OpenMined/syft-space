<template>
  <Hint v-if="hint" :text="hint.title">
    <span class="text-xs text-muted-foreground whitespace-nowrap" data-testid="utc-stamp-hint">
      {{ hint.label }}
    </span>
  </Hint>
</template>

<script setup lang="ts">
/** Local-time hint for a path containing a `YYYY-MM-DD_HHMM_UTC` segment; renders nothing otherwise. */
import { computed } from 'vue'
import Hint from '@/components/benchmark/Hint.vue'
import { utcStampHintForPath, type UtcStampFormatOptions } from '@/lib/utcStamp'

const props = defineProps<{
  path: string
  locale?: UtcStampFormatOptions['locale']
  timeZone?: UtcStampFormatOptions['timeZone']
}>()

const hint = computed(() =>
  utcStampHintForPath(props.path, { locale: props.locale, timeZone: props.timeZone }),
)
</script>
