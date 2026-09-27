<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { toast } from "vue-sonner";
import { listResults, overrideVerdict } from "@/api/console";
import type { ResultResponse, Verdict } from "@/api/types";
import { ApiError } from "@/api/client";

const props = defineProps<{ refreshKey: number }>();

const PAGE = 20;
const items = ref<ResultResponse[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const busyId = ref<string | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  try {
    const page = await listResults({ limit: PAGE, offset: offset.value });
    items.value = page.items;
    total.value = page.total;
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not load results",
    );
  } finally {
    loading.value = false;
  }
}

watch([() => props.refreshKey, offset], load, { immediate: true });

async function override(row: ResultResponse, verdict: Verdict): Promise<void> {
  const reasoning = window.prompt("Why? (shown next to the verdict)", "") ?? "";
  busyId.value = row.id;
  try {
    await overrideVerdict(row.id, verdict, reasoning);
    toast.success("Verdict overridden");
    await load();
  } catch (error) {
    toast.error(
      error instanceof ApiError
        ? error.message
        : "Could not override this verdict",
    );
  } finally {
    busyId.value = null;
  }
}

const hasMore = computed(() => offset.value + items.value.length < total.value);
</script>

<template>
  <div class="space-y-2">
    <p class="text-xs text-muted-foreground">{{ total }} result(s)</p>
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
        v-for="row in items"
        :key="row.id"
        class="rounded-md border border-border/60 p-2.5 text-sm space-y-1"
        :class="{ 'opacity-50': !row.is_latest }"
      >
        <div class="flex items-start gap-2">
          <div class="flex-1 min-w-0">
            <p class="font-medium break-words">{{ row.question }}</p>
            <p class="text-muted-foreground break-words">{{ row.answer }}</p>
          </div>
          <span
            class="shrink-0 rounded px-1.5 py-0.5 text-xs"
            :class="{
              'bg-success/20 text-success': row.verdict === 'correct',
              'bg-destructive/20 text-destructive':
                row.verdict === 'hallucinate',
              'bg-muted text-muted-foreground':
                row.verdict === 'abstain' || row.verdict === 'pending',
            }"
          >
            {{ row.verdict }}
          </span>
        </div>
        <p v-if="row.reasoning" class="text-xs text-muted-foreground italic">
          {{ row.reasoning }}
        </p>
        <div class="flex items-center gap-2 pt-1">
          <span class="text-xs text-muted-foreground"
            >{{ row.model }} · {{ row.context_mode }}</span
          >
          <span v-if="!row.is_latest" class="text-xs text-muted-foreground"
            >superseded</span
          >
          <template v-if="row.is_latest">
            <button
              v-if="row.verdict !== 'correct'"
              type="button"
              class="ml-auto text-xs rounded border border-border px-2 py-0.5 hover:bg-accent disabled:opacity-50"
              :disabled="busyId === row.id"
              @click="override(row, 'correct')"
            >
              Mark correct
            </button>
            <button
              v-if="row.verdict !== 'hallucinate'"
              type="button"
              class="text-xs rounded border border-border px-2 py-0.5 hover:bg-accent disabled:opacity-50"
              :class="{ 'ml-auto': row.verdict === 'correct' }"
              :disabled="busyId === row.id"
              @click="override(row, 'hallucinate')"
            >
              Mark hallucination
            </button>
          </template>
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
