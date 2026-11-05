<script setup lang="ts">
/** One short line of explanation behind an (i) button, on demand rather than printed in full. */
import { Info } from 'lucide-vue-next'
import Hint from './Hint.vue'

defineProps<{ text: string }>()
</script>

<template>
  <Hint :text="text">
    <button type="button" class="text-muted-foreground hover:text-foreground" :aria-label="text">
      <Info class="h-3.5 w-3.5" />
    </button>
  </Hint>
</template>
