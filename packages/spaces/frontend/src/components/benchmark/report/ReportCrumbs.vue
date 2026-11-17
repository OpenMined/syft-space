<template>
  <nav
    aria-label="Breadcrumb"
    class="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
  >
    <template v-for="(crumb, i) in crumbs" :key="i">
      <RouterLink
        v-if="crumb.to && i < crumbs.length - 1"
        :to="crumb.to"
        class="underline underline-offset-4 hover:text-foreground"
      >
        {{ crumb.label }}
      </RouterLink>
      <span v-else aria-current="page" class="text-foreground">{{ crumb.label }}</span>
      <span v-if="i < crumbs.length - 1" aria-hidden="true">›</span>
    </template>
  </nav>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

defineProps<{ crumbs: { label: string; to?: RouteLocationRaw }[] }>()
</script>
