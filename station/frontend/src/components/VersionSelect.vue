<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { PencilLine } from 'lucide-vue-next'
import { imagesApi } from '@/api/endpoints/images'
import type { ImageTagResponse } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

/**
 * Picker for the syft-space version (image tag), fed by the registry via
 * the backend's image catalog. Falls back to a free-text input when the
 * registry can't be reached — an air-gapped station still works.
 */
const model = defineModel<string>({ required: true })

const images = ref<ImageTagResponse[]>([])
const loading = ref(true)
const manual = ref(false)

const options = computed<ImageTagResponse[]>(() => {
  // Keep the currently configured tag selectable even when it has aged out
  // of the newest-five list.
  if (model.value && !images.value.some((i) => i.tag === model.value)) {
    return [{ tag: model.value, created: '', revision: null, is_latest: false }, ...images.value]
  }
  return images.value
})

function formatDate(iso: string): string {
  if (!iso) return 'currently configured'
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

onMounted(async () => {
  try {
    images.value = await imagesApi.list()
    // Nothing picked yet: default to the build "latest" points at.
    if (!model.value && images.value.length > 0) {
      model.value = (images.value.find((i) => i.is_latest) ?? images.value[0]!).tag
    }
  } catch {
    manual.value = true // registry unreachable — type the tag instead
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Input v-if="manual" v-model="model" placeholder="Image tag, e.g. 2fa954d" class="font-mono" />

  <div v-else class="flex items-center gap-1.5">
    <Select v-model="model" :disabled="loading">
      <SelectTrigger class="w-full">
        <SelectValue :placeholder="loading ? 'Loading versions…' : 'Pick a version'" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem v-for="image in options" :key="image.tag" :value="image.tag">
          <span class="flex items-center gap-2">
            <span class="font-mono">{{ image.tag }}</span>
            <span class="text-xs text-muted-foreground">{{ formatDate(image.created) }}</span>
            <Badge v-if="image.is_latest" variant="secondary" class="h-4 px-1.5 text-[10px]">
              latest
            </Badge>
          </span>
        </SelectItem>
      </SelectContent>
    </Select>
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
