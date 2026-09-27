<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Trash2 } from "lucide-vue-next";
import { toast } from "vue-sonner";
import { deletePair, listPairs, updatePairStatus } from "@/api/console";
import type { PairResponse, PairStatus } from "@/api/types";
import { ApiError } from "@/api/client";

// Shared by the Generation and Filtering blocks — they show the same rows,
// just pre-filtered to a different status by the parent.
const props = defineProps<{ status?: PairStatus; refreshKey: number }>();

const PAGE = 20;
const items = ref<PairResponse[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const busyId = ref<string | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  try {
    const page = await listPairs({
      status: props.status,
      limit: PAGE,
      offset: offset.value,
    });
    items.value = page.items;
    total.value = page.total;
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not load pairs",
    );
  } finally {
    loading.value = false;
  }
}

watch([() => props.status, () => props.refreshKey, offset], load, {
  immediate: true,
});

async function setStatus(
  pair: PairResponse,
  status: PairStatus,
): Promise<void> {
  busyId.value = pair.id;
  try {
    const updated = await updatePairStatus(pair.id, status);
    items.value = items.value.map((row) =>
      row.id === updated.id ? updated : row,
    );
    toast.success(`Marked ${status}`);
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not change status",
    );
  } finally {
    busyId.value = null;
  }
}

async function remove(pair: PairResponse): Promise<void> {
  if (!window.confirm(`Delete this pair for good? This cannot be undone.`))
    return;
  busyId.value = pair.id;
  try {
    await deletePair(pair.id);
    items.value = items.value.filter((row) => row.id !== pair.id);
    total.value -= 1;
    toast.success("Deleted");
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not delete this pair",
    );
  } finally {
    busyId.value = null;
  }
}

const hasMore = computed(() => offset.value + items.value.length < total.value);
</script>

<template>
  <div class="space-y-2">
    <p class="text-xs text-muted-foreground">{{ total }} pair(s)</p>
    <p
      v-if="loading && items.length === 0"
      class="text-sm text-muted-foreground"
    >
      Loading…
    </p>
    <p v-else-if="items.length === 0" class="text-sm text-muted-foreground">
      Nothing here yet.
    </p>
    <ul v-else class="space-y-2">
      <li
        v-for="pair in items"
        :key="pair.id"
        class="rounded-md border border-border/60 p-2.5 text-sm space-y-1"
      >
        <div class="flex items-start gap-2">
          <div class="flex-1 min-w-0">
            <p class="font-medium break-words">{{ pair.question }}</p>
            <p class="text-muted-foreground break-words">{{ pair.answer }}</p>
          </div>
          <span
            class="shrink-0 rounded px-1.5 py-0.5 text-xs"
            :class="{
              'bg-success/20 text-success': pair.status === 'active',
              'bg-destructive/20 text-destructive': pair.status === 'rejected',
              'bg-muted text-muted-foreground':
                pair.status === 'pending' || pair.status === 'retired',
            }"
          >
            {{ pair.status }}
          </span>
        </div>
        <p v-if="pair.status_note" class="text-xs text-muted-foreground italic">
          {{ pair.status_note }}
        </p>
        <div class="flex items-center gap-2 pt-1">
          <span class="text-xs text-muted-foreground">{{
            pair.generator
          }}</span>
          <button
            v-if="pair.status !== 'active'"
            type="button"
            class="ml-auto text-xs rounded border border-border px-2 py-0.5 hover:bg-accent disabled:opacity-50"
            :disabled="busyId === pair.id"
            @click="setStatus(pair, 'active')"
          >
            Mark active
          </button>
          <button
            v-if="pair.status !== 'rejected'"
            type="button"
            class="text-xs rounded border border-border px-2 py-0.5 hover:bg-accent disabled:opacity-50"
            :disabled="busyId === pair.id"
            @click="setStatus(pair, 'rejected')"
          >
            Reject
          </button>
          <button
            type="button"
            class="text-xs rounded border border-border p-1 text-destructive hover:bg-destructive/10 disabled:opacity-30"
            :disabled="busyId === pair.id || pair.has_results"
            :title="
              pair.has_results
                ? 'Has results — change its status instead of deleting'
                : 'Delete for good'
            "
            @click="remove(pair)"
          >
            <Trash2 :size="14" />
          </button>
        </div>
      </li>
    </ul>
    <div v-if="offset > 0 || hasMore" class="flex items-center gap-2 text-xs">
      <button
        type="button"
        class="rounded border border-border px-2 py-1 disabled:opacity-40"
        :disabled="offset === 0"
        @click="offset = Math.max(0, offset - PAGE)"
      >
        Previous
      </button>
      <button
        type="button"
        class="rounded border border-border px-2 py-1 disabled:opacity-40"
        :disabled="!hasMore"
        @click="offset += PAGE"
      >
        Next
      </button>
    </div>
  </div>
</template>
