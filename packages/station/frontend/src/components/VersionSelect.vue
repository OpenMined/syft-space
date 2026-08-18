<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { PencilLine, RefreshCw } from 'lucide-vue-next'
import type { ImageTagResponse } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useStationStore } from '@/stores/station'

/**
 * Picker for the syft-space version (image tag), fed by the registry via
 * the station store's session-cached catalog. The tag currently held by
 * the model stays pinned at the top — a fetch never displaces it — with
 * the registry list below a separator. Falls back to a free-text input
 * when the registry can't be reached — an air-gapped station still works.
 */
const model = defineModel<string>({ required: true })

const station = useStationStore()

const manual = ref(false)
const refreshing = ref(false)

/** The model's tag, enriched with registry metadata when the catalog has it. */
const current = computed<ImageTagResponse | null>(() => {
  if (!model.value) return null
  return (
    station.imageTags.find((i) => i.tag === model.value) ?? {
      tag: model.value,
      created: '',
      revision: null,
      is_latest: false,
    }
  )
})

/** Registry tags, minus the pinned current one. */
const fetched = computed<ImageTagResponse[]>(() =>
  station.imageTags.filter((i) => i.tag !== model.value),
)

function formatDate(iso: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

async function load(refresh = false): Promise<void> {
  refreshing.value = refresh
  try {
    await station.loadImageTags(refresh)
    // Nothing picked yet (first-run setup): default to the build "latest"
    // points at. Never overrides a tag the model already holds.
    if (!model.value && station.imageTags.length > 0) {
      model.value = (station.imageTags.find((i) => i.is_latest) ?? station.imageTags[0]!).tag
    }
  } catch {
    manual.value = true // registry unreachable — type the tag instead
  } finally {
    refreshing.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <Input v-if="manual" v-model="model" placeholder="Image tag, e.g. 2fa954d" class="font-mono" />

  <div v-else class="flex items-center gap-1.5">
    <Select v-model="model" :disabled="station.imageTagsLoading && !refreshing">
      <SelectTrigger class="w-full">
        <SelectValue :placeholder="station.imageTagsLoading ? 'Loading versions…' : 'Pick a version'" />
      </SelectTrigger>
      <SelectContent>
        <template v-if="current">
          <SelectItem :value="current.tag">
            <span class="font-mono">{{ current.tag }}</span>
            <template #trailing>
              <span v-if="current.created" class="text-xs text-muted-foreground">
                {{ formatDate(current.created) }}
              </span>
              <Badge variant="outline" class="h-4 px-1.5 text-[10px]">current</Badge>
            </template>
          </SelectItem>
          <SelectSeparator v-if="fetched.length" class="h-0 border-t border-dashed bg-transparent" />
        </template>
        <SelectItem v-for="image in fetched" :key="image.tag" :value="image.tag">
          <span class="font-mono">{{ image.tag }}</span>
          <template #trailing>
            <span class="text-xs text-muted-foreground">{{ formatDate(image.created) }}</span>
            <Badge v-if="image.is_latest" variant="secondary" class="h-4 px-1.5 text-[10px]">
              latest
            </Badge>
          </template>
        </SelectItem>
      </SelectContent>
    </Select>
    <Button
      variant="ghost"
      size="icon"
      class="h-9 w-9 shrink-0"
      title="Re-check the registry for new tags"
      :disabled="refreshing"
      @click="load(true)"
    >
      <RefreshCw class="h-3.5 w-3.5" :class="refreshing ? 'animate-spin' : ''" />
    </Button>
    <Button
      variant="ghost"
      size="icon"
      class="h-9 w-9 shrink-0"
      title="Type a tag instead"
      @click="manual = true"
    >
      <PencilLine class="h-3.5 w-3.5" />
    </Button>
  </div>
</template>
