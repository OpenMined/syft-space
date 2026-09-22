<script setup lang="ts">
/**
 * The headline numbers as one divided surface, not N cards. Four separate
 * cards give four borders competing with the tables below them; a strip
 * reads as a single header line for the view.
 */
defineProps<{
  stats: { label: string; value: string; hint?: string; accent?: boolean }[]
}>()
</script>

<template>
  <dl
    class="grid grid-cols-2 divide-x divide-y rounded-lg border bg-card sm:grid-cols-4 sm:divide-y-0"
  >
    <div v-for="stat in stats" :key="stat.label" class="px-4 py-3">
      <dt class="text-xs text-muted-foreground">{{ stat.label }}</dt>
      <dd
        class="mt-1 text-xl font-semibold tracking-tight tabular-nums"
        :class="stat.accent ? 'text-primary' : ''"
      >
        {{ stat.value }}
        <span v-if="stat.hint" class="text-sm font-normal text-muted-foreground">
          · {{ stat.hint }}
        </span>
      </dd>
    </div>
  </dl>
</template>
