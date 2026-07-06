<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">Add source</DialogTitle>
        <DialogDescription>
          Select new items to ingest. Items already selected are shown checked and can't be removed
          here.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Source browser: already-selected items are locked; pick new ones to add -->
        <SourceBrowser
          v-if="dataset"
          ref="sourceBrowserRef"
          :key="dataset.name"
          :dtype="dataset.dtype"
          :dataset-name="dataset.name"
          :locked-selection="dataset.selectedIds"
          v-model="selectedFiles"
        />

        <!-- Per-item descriptions for newly-added items -->
        <div v-if="selectedFiles.length > 0" class="space-y-3">
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-medium text-foreground">New items</h4>
            <Badge variant="secondary" class="text-xs">{{ selectedFiles.length }}</Badge>
          </div>

          <div class="rounded-lg border border-border bg-muted/30 divide-y divide-border">
            <div
              v-for="file in selectedFiles"
              :key="file"
              class="p-4 first:rounded-t-lg last:rounded-b-lg hover:bg-muted/50 transition-colors"
            >
              <div class="flex items-start gap-3">
                <div class="flex h-9 w-9 items-center justify-center rounded-md bg-muted shrink-0">
                  <component
                    :is="getFileIcon(file, false, sourceBrowserRef?.rootNodes)"
                    class="h-4 w-4"
                    :class="getFileIconColor(file, sourceBrowserRef?.rootNodes)"
                  />
                </div>
                <div class="flex-1 min-w-0 space-y-3">
                  <div class="space-y-1">
                    <p class="text-sm font-medium text-foreground truncate">
                      {{ getFileName(file) }}
                    </p>
                    <p class="text-xs text-muted-foreground truncate">{{ file }}</p>
                  </div>
                  <Input
                    v-model="fileDescriptions[file]"
                    placeholder="Add a description (optional)..."
                    class="text-sm h-9 bg-background"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="mt-8">
        <Button variant="outline" @click="handleCancel">Cancel</Button>
        <Button @click="handleAdd" :disabled="!canAdd">
          {{ isAdding ? 'Adding...' : 'Add source' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import SourceBrowser from '@/components/SourceBrowser.vue'
import { useFileIcon } from '@/composables/useFileIcon'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { SelectionItemRequest } from '@/api/types'

const props = withDefaults(
  defineProps<{
    open: boolean
    dataset: {
      name: string
      dtype: string
      selectedIds: string[]
    } | null
  }>(),
  { dataset: null },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  'sources-added': []
}>()

const { getFileIcon, getFileIconColor } = useFileIcon()
const sourceBrowserRef = ref<InstanceType<typeof SourceBrowser> | null>(null)
const selectedFiles = ref<string[]>([])
const fileDescriptions = ref<Record<string, string>>({})
const isAdding = ref(false)

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const canAdd = computed(() => !isAdding.value && selectedFiles.value.length > 0)

const getFileName = (path: string) => path.split('/').pop() || path

const reset = () => {
  selectedFiles.value = []
  fileDescriptions.value = {}
}

const handleCancel = () => {
  reset()
  isOpen.value = false
}

const handleAdd = async () => {
  if (!props.dataset || !canAdd.value) return

  isAdding.value = true
  try {
    const items: SelectionItemRequest[] = selectedFiles.value.map((id) => ({
      item_id: id,
      description: fileDescriptions.value[id] || '',
    }))

    await datasetsApi.addSelection(props.dataset.name, items)
    emit('sources-added')
    toast.success(
      `Added ${items.length} source${items.length !== 1 ? 's' : ''} to "${props.dataset.name}"`,
    )
    reset()
    isOpen.value = false
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error occurred'
    toast.error(`Failed to add sources: ${message}`)
  } finally {
    isAdding.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (!open) reset()
  },
)
</script>
