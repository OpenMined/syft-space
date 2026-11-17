<script setup lang="ts">
/** How one kind's writing went in a job. */
import type { BenchmarkKindBuild } from '@/api/types'
import { KIND_BUILD_STATS } from '../../filter'
import Hint from '../../Hint.vue'
import KindBuildValue from './KindBuildValue.vue'

defineProps<{ build: BenchmarkKindBuild }>()
</script>

<template>
  <dl class="flex flex-wrap gap-x-6 gap-y-2 text-sm" data-testid="kind-build-stats">
    <div v-for="stat in KIND_BUILD_STATS" :key="stat.key">
      <Hint :text="stat.tip">
        <dt class="text-xs text-muted-foreground">{{ stat.label }}</dt>
      </Hint>
      <dd><KindBuildValue :build="build" :stat="stat.key" /></dd>
    </div>
  </dl>
</template>
