<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">{{
          props.dataset ? 'Edit Data Source' : 'Add Data Source'
        }}</DialogTitle>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Name -->
        <div class="space-y-2">
          <Label for="dataset-name" class="text-sm font-medium">
            Name <span class="text-red-500">*</span>
          </Label>
          <Input
            id="dataset-name"
            v-model="formData.name"
            placeholder="e.g., legal-documents"
            class="w-full"
          />
        </div>

        <!-- Source-specific browser -->
        <div v-if="!props.dataset" class="space-y-4">
          <SourceBrowser
            :key="sourceType"
            ref="sourceBrowserRef"
            :dtype="sourceType"
            :configuration="browserConfiguration"
            v-model="formData.selectedFiles"
          />

          <!-- Per-file descriptions (local_file only) -->
          <div
            v-if="sourceType === 'local_file' && formData.selectedFiles.length > 0"
            class="space-y-3"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <h4 class="text-sm font-medium text-foreground">Selected Items</h4>
                <Badge variant="secondary" class="text-xs">
                  {{ formData.selectedFiles.length }}
                </Badge>
              </div>
              <Button
                v-if="!props.dataset"
                @click="clearAllFiles"
                variant="ghost"
                size="sm"
                class="h-8 text-xs text-muted-foreground hover:text-destructive"
              >
                <X class="h-3 w-3 mr-1" />
                Clear all
              </Button>
            </div>

            <div class="rounded-lg border border-border bg-muted/30 divide-y divide-border">
              <div
                v-for="(file, index) in formData.selectedFiles"
                :key="file"
                class="p-4 first:rounded-t-lg last:rounded-b-lg hover:bg-muted/50 transition-colors"
              >
                <div class="flex items-start gap-3">
                  <div
                    class="flex h-9 w-9 items-center justify-center rounded-md bg-muted flex-shrink-0"
                  >
                    <component
                      :is="getFileIcon(file, false, sourceBrowserRef?.rootNodes)"
                      class="h-4 w-4"
                      :class="getFileIconColor(file, sourceBrowserRef?.rootNodes)"
                    />
                  </div>
                  <div class="flex-1 min-w-0 space-y-3">
                    <div class="flex items-start justify-between gap-2">
                      <div class="space-y-1">
                        <p class="text-sm font-medium text-foreground truncate">
                          {{ getFileName(file) }}
                        </p>
                        <p class="text-xs text-muted-foreground truncate">
                          {{ file }}
                        </p>
                      </div>
                      <Button
                        v-if="!props.dataset"
                        @click="removeFile(index)"
                        variant="ghost"
                        size="sm"
                        class="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10 flex-shrink-0"
                      >
                        <X class="h-4 w-4" />
                      </Button>
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

        <!-- Summary -->
        <div class="space-y-2">
          <Label for="summary" class="text-sm font-medium"> Summary </Label>
          <Input
            id="summary"
            v-model="formData.summary"
            placeholder="What does this data source contain?"
            class="w-full"
          />
        </div>

        <!-- Tags -->
        <div class="space-y-2">
          <Label for="topics" class="text-sm font-medium"> Tags </Label>
          <div class="space-y-2">
            <div class="flex gap-2">
              <Input
                id="topics"
                v-model="tagInput"
                @keydown.enter.prevent="addTag"
                placeholder="e.g., legal, medical, research"
                class="flex-1"
              />
              <Button @click="addTag" variant="outline" :disabled="!tagInput.trim()">
                <Plus class="h-4 w-4" />
              </Button>
            </div>

            <!-- Popular Tags Suggestions -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs text-muted-foreground">Popular:</span>
              <Button
                v-for="suggestion in popularTags"
                :key="suggestion"
                @click="addSuggestedTag(suggestion)"
                variant="ghost"
                size="sm"
                class="h-6 px-2 text-xs"
                :disabled="formData.tags.includes(suggestion)"
              >
                {{ suggestion }}
              </Button>
            </div>

            <!-- Selected Tags -->
            <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-3">
              <Badge
                v-for="(tag, index) in formData.tags"
                :key="index"
                variant="secondary"
                class="px-3 py-1"
              >
                {{ tag }}
                <button
                  @click="removeTag(index)"
                  class="ml-2 hover:text-destructive transition-colors"
                >
                  <X class="h-3 w-3" />
                </button>
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="mt-8">
        <Button variant="outline" @click="handleCancel"> Cancel </Button>
        <Button @click="handleCreate" :disabled="!isFormValid">
          {{
            isCreating
              ? props.dataset
                ? 'Saving...'
                : 'Adding...'
              : props.dataset
                ? 'Save Changes'
                : 'Add Data Source'
          }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Plus, X } from 'lucide-vue-next'
import SourceBrowser from '@/components/SourceBrowser.vue'
import { useFileIcon } from '@/composables/useFileIcon'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { CreateDatasetRequest, SelectionItemRequest, UpdateDatasetRequest } from '@/api/types'

interface EditDataset {
  id: string
  name: string
  summary: string
  tags: string[]
}

const props = withDefaults(
  defineProps<{
    open: boolean
    dataset?: EditDataset | null
    sourceType?: string
    credentials?: Record<string, string>
  }>(),
  {
    dataset: null,
    sourceType: 'local_file',
    credentials: () => ({}),
  },
)

const sourceType = computed(() => props.sourceType)
const credentials = computed(() => props.credentials)

const browserConfiguration = computed<Record<string, unknown>>(() => {
  if (sourceType.value === 'wordpress') {
    return {
      siteUrl: credentials.value.siteUrl ?? '',
      username: credentials.value.username ?? '',
      applicationPassword: credentials.value.applicationPassword ?? '',
    }
  }
  return {}
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  'dataset-created': []
  'dataset-updated': []
}>()

const popularTags = ['legal', 'medical', 'research', 'finance', 'education', 'news', 'technical']

const formData = ref({
  name: '',
  summary: '',
  selectedFiles: [] as string[],
  tags: [] as string[],
})

const tagInput = ref('')
const fileDescriptions = ref<Record<string, string>>({})
const { getFileIcon, getFileIconColor } = useFileIcon()
const sourceBrowserRef = ref<InstanceType<typeof SourceBrowser> | null>(null)
const isCreating = ref(false)
const isInitialized = ref(false)

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const isFormValid = computed(() => {
  if (isCreating.value) return false
  if (props.dataset) {
    return formData.value.name.trim() !== ''
  }
  return formData.value.name.trim() !== '' && formData.value.selectedFiles.length > 0
})

const buildConfiguration = (): Record<string, unknown> => {
  if (sourceType.value === 'wordpress') {
    return {
      siteUrl: credentials.value.siteUrl ?? '',
      username: credentials.value.username ?? '',
      applicationPassword: credentials.value.applicationPassword ?? '',
    }
  }
  // local_file (default) — no source-specific config beyond defaults; the
  // selection travels in selected_items, not in the configuration.
  return {}
}

// The picker selection, sent as selected_items (stored server-side in the
// dataset_selection table, never inside configuration).
const buildSelectedItems = (): SelectionItemRequest[] =>
  formData.value.selectedFiles.map((itemId) => ({
    item_id: itemId,
    description: fileDescriptions.value[itemId] || '',
  }))

const getFileName = (path: string) => {
  return path.split('/').pop() || path
}

const removeFile = (index: number) => {
  const file = formData.value.selectedFiles[index]
  formData.value.selectedFiles.splice(index, 1)
  if (file && fileDescriptions.value[file]) {
    delete fileDescriptions.value[file]
  }
}

const clearAllFiles = () => {
  formData.value.selectedFiles = []
  fileDescriptions.value = {}
}

const addTag = () => {
  const tag = tagInput.value.trim().toLowerCase()
  if (tag && !formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
    tagInput.value = ''
  }
}

const addSuggestedTag = (tag: string) => {
  if (!formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
  }
}

const removeTag = (index: number) => {
  formData.value.tags.splice(index, 1)
}

const handleCancel = () => {
  resetForm()
  isOpen.value = false
}

const handleCreate = async () => {
  if (!isFormValid.value) return

  isCreating.value = true

  try {
    if (props.dataset) {
      const updateRequest: UpdateDatasetRequest = {
        name: formData.value.name.trim(),
        summary: formData.value.summary.trim() || '',
        tags: formData.value.tags.join(','),
      }

      await datasetsApi.update(props.dataset.name, updateRequest)
      emit('dataset-updated')
      toast.success(`"${props.dataset.name}" updated`)
    } else {
      const createRequest: CreateDatasetRequest = {
        dtype: sourceType.value,
        name: formData.value.name.trim(),
        summary: formData.value.summary.trim() || '',
        tags: formData.value.tags.join(','),
        configuration: buildConfiguration(),
        selected_items: buildSelectedItems(),
      }

      await datasetsApi.create(createRequest)
      emit('dataset-created')
      toast.success(`"${createRequest.name}" added`)
    }

    resetForm()
    isOpen.value = false
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
    const action = props.dataset ? 'save' : 'add'
    toast.error(`Failed to ${action} data source: ${errorMessage}`)
  } finally {
    isCreating.value = false
  }
}

const resetForm = () => {
  formData.value = {
    name: '',
    summary: '',
    selectedFiles: [],
    tags: [],
  }
  tagInput.value = ''
  fileDescriptions.value = {}
  isInitialized.value = false
}

watch(
  () => [props.open, props.dataset] as const,
  async ([open, dataset]) => {
    if (open && dataset && !isInitialized.value) {
      await nextTick()

      formData.value = {
        name: dataset.name,
        summary: dataset.summary || '',
        selectedFiles: [], // Not used in edit mode
        tags: [...dataset.tags],
      }
      fileDescriptions.value = {} // Not used in edit mode
      isInitialized.value = true
    } else if (open && !dataset) {
      isInitialized.value = false
      resetForm()
    } else if (!open) {
      isInitialized.value = false
    }
  },
  { immediate: true },
)
</script>
