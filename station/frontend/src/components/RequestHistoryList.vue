<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import RequestHistoryRow from '@/components/RequestHistoryRow.vue'
import type { SpaceRequest } from '@/lib/types'

// Settled-request history as a divided list inside a bounded scroll area, with
// a "Load more" button that reveals the next page. Client-side paging over the
// already-loaded requests (the whole set lives in the store); it can move to a
// server cursor later without changing this component's shape.
const props = withDefaults(
  defineProps<{ requests: SpaceRequest[]; showRequester?: boolean; pageSize?: number }>(),
  { pageSize: 10 },
)

const visible = ref(props.pageSize)

// If the list shrinks below what we're showing (a request settled elsewhere,
// a refetch), clamp back so we never slice past the end.
watch(
  () => props.requests.length,
  (n) => {
    if (visible.value > n) visible.value = Math.max(props.pageSize, Math.min(visible.value, n))
  },
)

const shown = computed(() => props.requests.slice(0, visible.value))
const remaining = computed(() => Math.max(0, props.requests.length - visible.value))
</script>

<template>
  <div class="space-y-2">
    <div class="max-h-96 divide-y overflow-y-auto rounded-md border">
      <RequestHistoryRow
        v-for="request in shown"
        :key="request.id"
        :request="request"
        :show-requester="showRequester"
      />
    </div>
    <div v-if="remaining > 0" class="flex justify-center">
      <Button
        variant="ghost"
        size="sm"
        class="text-xs text-muted-foreground"
        @click="visible += pageSize"
      >
        Load more ({{ remaining }})
      </Button>
    </div>
  </div>
</template>
