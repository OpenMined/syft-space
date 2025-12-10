<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">Create Dataset</DialogTitle>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Dataset Name -->
        <div class="space-y-2">
          <Label for="dataset-name" class="text-sm font-medium">
            Dataset Name <span class="text-red-500">*</span>
          </Label>
          <Input id="dataset-name" v-model="formData.name" placeholder="e.g., Legal Documents Store" class="w-full" />
          <p class="text-sm text-muted-foreground">
            Give your dataset a descriptive name
          </p>
        </div>

        <!-- File Explorer -->
        <div class="space-y-4">
          <FileExplorer v-model="formData.selectedFiles" :show-hidden="false" :allow-multiple="true" />

          <!-- Selected Items with Descriptions -->
          <div v-if="formData.selectedFiles.length > 0" class="border-t pt-4 space-y-3">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-medium text-foreground">
                Selected Items ({{ formData.selectedFiles.length }})
              </h4>
              <Button @click="clearAllFiles" variant="ghost" size="sm"
                class="text-muted-foreground hover:text-foreground">
                Clear all
              </Button>
            </div>

            <div class="space-y-3">
              <div v-for="file in formData.selectedFiles" :key="file"
                class="p-3 bg-muted/50 border border-border rounded-lg">
                <div class="flex items-start gap-3">
                  <FileText class="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                  <div class="flex-1 min-w-0 space-y-2">
                    <div class="flex items-center justify-between gap-2">
                      <p class="text-sm font-medium text-foreground truncate">{{ getFileName(file) }}</p>
                      <Button @click="removeFile(formData.selectedFiles.indexOf(file))" variant="ghost" size="sm"
                        class="h-6 w-6 p-0 hover:text-destructive">
                        <X class="h-3 w-3" />
                      </Button>
                    </div>
                    <div class="space-y-1">
                      <Label class="text-sm text-muted-foreground">Description (Optional)</Label>
                      <Input v-model="fileDescriptions[file]" placeholder="Brief description of this item's content..."
                        class="text-sm" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Summary -->
        <div class="space-y-2">
          <Label for="summary" class="text-sm font-medium">
            Summary (Optional)
          </Label>
          <Input id="summary" v-model="formData.summary"
            placeholder="Describe what this dataset contains and how it can be used..." class="w-full" />
          <p class="text-sm text-muted-foreground">
            A brief description of your dataset's contents
          </p>
        </div>

        <!-- Topics & Categories -->
        <div class="space-y-2">
          <Label for="topics" class="text-sm font-medium">
            Topics & Categories (Optional)
          </Label>
          <div class="space-y-2">
            <div class="flex gap-2">
              <Input id="topics" v-model="tagInput" @keydown.enter.prevent="addTag"
                placeholder="Add keywords like: legal, medical, research, finance" class="flex-1" />
              <Button @click="addTag" variant="outline" :disabled="!tagInput.trim()">
                <Plus class="h-4 w-4" />
              </Button>
            </div>

            <!-- Popular Tags Suggestions -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs text-muted-foreground">Popular:</span>
              <Button v-for="suggestion in popularTags" :key="suggestion" @click="addSuggestedTag(suggestion)"
                variant="ghost" size="sm" class="h-6 px-2 text-xs" :disabled="formData.tags.includes(suggestion)">
                {{ suggestion }}
              </Button>
            </div>

            <!-- Selected Tags -->
            <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-3">
              <Badge v-for="(tag, index) in formData.tags" :key="index" variant="secondary" class="px-3 py-1">
                {{ tag }}
                <button @click="removeTag(index)" class="ml-2 hover:text-destructive transition-colors">
                  <X class="h-3 w-3" />
                </button>
              </Badge>
            </div>
          </div>
          <p class="text-sm text-muted-foreground">
            Tags help others discover your dataset
          </p>
        </div>
      </div>

      <DialogFooter class="mt-8">
        <Button variant="outline" @click="handleCancel">
          Cancel
        </Button>
        <Button @click="handleCreate" :disabled="!isFormValid">
          {{ isCreating ? 'Creating...' : 'Create Dataset' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
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
import { FileText, Plus, X } from 'lucide-vue-next'
import FileExplorer from '@/components/FileExplorer.vue'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { CreateDatasetRequest } from '@/api/types'

interface DataSource {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
}

const props = defineProps<{
  open: boolean
  dataset?: DataSource | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'dataset-created': []
  'dataset-updated': []
}>()

// Popular tag suggestions
const popularTags = ['legal', 'medical', 'research', 'finance', 'education', 'news', 'technical']

// Form data
const formData = ref({
  name: '',
  summary: '',
  selectedFiles: [] as string[],
  tags: [] as string[],
})

const tagInput = ref('')
const fileDescriptions = ref<Record<string, string>>({})
const isCreating = ref(false)

// Computed properties
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const isFormValid = computed(() => {
  return formData.value.name.trim() !== '' && formData.value.selectedFiles.length > 0 && !isCreating.value
})

// Utility function to generate collection name
const generateCollectionName = (name: string): string => {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '') // Remove non-alphanumeric characters except spaces
    .replace(/\s+/g, '_') // Replace spaces with underscores
    .replace(/_{2,}/g, '_') // Replace multiple underscores with single
    .replace(/^_|_$/g, '') // Remove leading/trailing underscores
}

// Methods
const getFileName = (path: string) => {
  return path.split('/').pop() || path
}

const removeFile = (index: number) => {
  const file = formData.value.selectedFiles[index]
  formData.value.selectedFiles.splice(index, 1)
  // Also remove the description
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
    const createRequest: CreateDatasetRequest = {
      dtype: 'local_file',
      name: formData.value.name.trim(),
      summary: formData.value.summary.trim() || '',
      tags: formData.value.tags.join(','),
      configuration: {
        collectionName: generateCollectionName(formData.value.name.trim()),
        filePaths: formData.value.selectedFiles,
      },
    }

    await datasetsApi.create(createRequest)

    if (props.dataset) {
      emit('dataset-updated')
      toast.success(`Dataset "${createRequest.name}" updated successfully`)
    } else {
      emit('dataset-created')
      toast.success(`Dataset "${createRequest.name}" created successfully`)
    }

    resetForm()
    isOpen.value = false
  } catch (error) {
    console.error('Failed to create dataset:', error)
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
    toast.error(`Failed to create dataset: ${errorMessage}`)
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
}

// Initialize form data if editing
if (props.dataset) {
  formData.value.name = props.dataset.name
  formData.value.tags = [...props.dataset.tags]
}
</script>