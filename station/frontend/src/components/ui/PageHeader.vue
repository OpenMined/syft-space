<template>
  <div class="page-header">
    <div class="page-title-section">
      <slot name="icon" />
      <h1 class="heading-3">
        <slot name="title" />
      </h1>
    </div>
    <div v-if="$slots.description" class="page-description">
      <slot name="description" />
    </div>
    <div v-if="$slots.actions" class="mt-6 flex items-center gap-3">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
// Reusable page header component with consistent styling
</script>
