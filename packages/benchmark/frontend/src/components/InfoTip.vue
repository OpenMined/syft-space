<script setup lang="ts">
import { ref } from "vue";
import { Info } from "lucide-vue-next";

// One short line of explanation, shown on demand rather than always on the
// page — the design brief for this console asked for minimal standing text,
// with detail available behind a small (?) rather than printed in full.
defineProps<{ text: string }>();

const open = ref(false);
</script>

<template>
  <span class="relative inline-flex">
    <button
      type="button"
      class="text-muted-foreground hover:text-foreground"
      :aria-label="text"
      @click="open = !open"
      @blur="open = false"
    >
      <Info :size="14" />
    </button>
    <span
      v-if="open"
      class="absolute z-10 top-5 left-0 w-64 rounded-md border border-border bg-card p-2 text-xs text-card-foreground shadow-lg"
    >
      {{ text }}
    </span>
  </span>
</template>
