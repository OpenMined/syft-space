<script setup lang="ts">
/** One figure of how a kind's writing went: written, read, dropped or why it stopped. */
import type { BenchmarkKindBuild } from '@/api/types'
import { droppedLines, droppedTotal, readText, writtenText, type KindBuildStat } from '../../filter'
import Hint from '../../Hint.vue'
import StopChip from './StopChip.vue'

defineProps<{ build: BenchmarkKindBuild; stat: KindBuildStat }>()
</script>

<template>
  <span v-if="stat === 'written'" class="tabular-nums" data-testid="kind-written">
    {{ writtenText(build) }}
  </span>
  <span v-else-if="stat === 'read'" class="tabular-nums text-muted-foreground">
    {{ readText(build) }}
  </span>
  <template v-else-if="stat === 'dropped'">
    <Hint v-if="droppedTotal(build)" :text="droppedLines(build).join('\n')">
      <span
        class="cursor-help tabular-nums underline decoration-dotted underline-offset-2"
        data-testid="kind-dropped"
        >{{ droppedTotal(build) }}</span
      >
    </Hint>
    <span v-else class="tabular-nums text-muted-foreground">0</span>
  </template>
  <StopChip v-else :stopped="build.stopped" />
</template>
