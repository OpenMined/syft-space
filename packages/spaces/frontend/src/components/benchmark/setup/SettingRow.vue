<template>
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border/60 py-2.5">
    <div class="flex min-w-0 flex-[1_1_320px] flex-col gap-0.5">
      <span class="flex items-center gap-1.5">
        <Label :for="forId || undefined" class="font-medium text-foreground">{{ label }}</Label>
        <InfoTip v-if="tip" :text="tip" />
      </span>
      <span v-if="help" class="text-xs text-muted-foreground">{{ help }}</span>
    </div>
    <div class="flex flex-[0_0_280px] items-center gap-2">
      <slot />
      <span v-if="unit" class="text-sm text-muted-foreground">{{ unit }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
/** One advanced setting: its name and help on the left, the control on the right. */
import InfoTip from '@/components/benchmark/InfoTip.vue'
import { Label } from '@/components/ui/label'

defineProps<{ label: string; help?: string; tip?: string; unit?: string; forId?: string }>()
</script>
