<script setup lang="ts">
import RequestStatusBadge from '@/components/RequestStatusBadge.vue'
import { REQUEST_TYPE_META } from '@/lib/requestTypes'
import type { SpaceRequest } from '@/lib/types'

// One row of the settled-request history. A divided-list row (no own border —
// the list container draws the hairlines) with the status aligned to the right.
// Rendered identically on the member and admin "History" lists; the admin also
// shows who made the request (showRequester).
defineProps<{ request: SpaceRequest; showRequester?: boolean }>()

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5">
    <component
      :is="REQUEST_TYPE_META[request.type].icon"
      class="h-3.5 w-3.5 shrink-0 text-muted-foreground"
    />
    <span class="text-sm font-medium">{{ request.spaceName }}</span>
    <span class="truncate text-xs text-muted-foreground">
      {{ REQUEST_TYPE_META[request.type].label
      }}<template v-if="showRequester"> · {{ request.requesterEmail }}</template> ·
      {{ formatDate(request.createdAt) }}
    </span>
    <RequestStatusBadge :status="request.status" class="ml-auto shrink-0" />
    <span v-if="request.resolutionNote" class="w-full text-xs text-muted-foreground">
      <span class="font-medium text-foreground">Admin note:</span> {{ request.resolutionNote }}
    </span>
  </div>
</template>
