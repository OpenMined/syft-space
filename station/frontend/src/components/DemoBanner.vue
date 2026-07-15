<script setup lang="ts">
import { FlaskConical } from 'lucide-vue-next'
</script>

<template>
  <div
    class="flex items-center justify-center gap-2 bg-warning/15 px-4 py-1.5 text-xs text-foreground/80 border-b border-warning/30"
  >
    <FlaskConical class="h-3.5 w-3.5 shrink-0" />
    <span>
      UX prototype — all data is mocked and resets on refresh. Approvals provision after a simulated
      delay; include “fail” in a subdomain to see the failure path.
    </span>
  </div>
</template>
