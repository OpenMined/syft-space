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

        <!-- Source type + data entry (new datasets only) -->
        <div v-if="!props.dataset" class="space-y-4">
          <div class="space-y-2">
            <Label for="source-type" class="text-sm font-medium">Source</Label>
            <Select v-model="sourceType">
              <SelectTrigger id="source-type" class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="local">Local files & folders</SelectItem>
                <SelectItem value="wordpress">Data connector — WordPress</SelectItem>
                <SelectItem value="rss">Data connector — RSS</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- WordPress connector -->
          <div v-if="sourceType === 'wordpress'" class="space-y-4">
            <div class="space-y-2">
              <Label for="wp-url" class="text-sm font-medium">
                Site URL <span class="text-red-500">*</span>
              </Label>
              <Input id="wp-url" v-model="wordpress.siteUrl" placeholder="https://blog.example.com" />
            </div>
            <div class="space-y-2">
              <Label for="wp-key" class="text-sm font-medium">
                API key <span class="text-red-500">*</span>
              </Label>
              <Input
                id="wp-key"
                v-model="wordpress.apiKey"
                type="password"
                placeholder="wp_xxxxxxxxxxxxxxxx"
              />
            </div>
            <p class="text-xs text-muted-foreground">
              Posts and pages are synced through the WordPress REST API. Demo UI only.
            </p>
          </div>

          <!-- RSS connector -->
          <div v-else-if="sourceType === 'rss'" class="space-y-3">
            <Label class="text-sm font-medium">
              Feed URLs <span class="text-red-500">*</span>
            </Label>
            <div v-for="(_, index) in rssFeeds" :key="index" class="flex gap-2">
              <Input
                v-model="rssFeeds[index]"
                placeholder="https://example.com/feed.xml"
                class="flex-1"
              />
              <Button
                v-if="rssFeeds.length > 1"
                @click="removeRssFeed(index)"
                variant="ghost"
                size="sm"
                class="h-9 w-9 p-0 text-muted-foreground hover:text-destructive"
              >
                <X class="h-4 w-4" />
              </Button>
            </div>
            <Button @click="addRssFeed" variant="outline" size="sm">
              <Plus class="h-4 w-4 mr-1" />
              Add feed
            </Button>
            <p class="text-xs text-muted-foreground">
              Each feed is polled and new items are ingested as documents. Demo UI only.
            </p>
          </div>

          <!-- Local files & folders -->
          <FileExplorer
            v-else
            ref="fileExplorerRef"
            v-model="formData.selectedFiles"
            :show-hidden="false"
            :allow-multiple="true"
          />

          <!-- Selected Items with Descriptions -->
          <div v-if="formData.selectedFiles.length > 0" class="space-y-3">
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
                      :is="getFileIcon(file, false, fileExplorerRef?.rootNodes)"
                      class="h-4 w-4"
                      :class="getFileIconColor(file, fileExplorerRef?.rootNodes)"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, X } from 'lucide-vue-next'
import FileExplorer from '@/components/FileExplorer.vue'
import { useFileIcon } from '@/composables/useFileIcon'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { CreateDatasetRequest, UpdateDatasetRequest } from '@/api/types'

interface EditDataset {
  id: string
  name: string
  summary: string
  tags: string[]
  filePaths: Array<{ path: string; description: string }>
}

const props = defineProps<{
  open: boolean
  dataset?: EditDataset | null
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

// Data source type. Connectors (wordpress/rss) are illustrative — UI only.
type SourceType = 'local' | 'wordpress' | 'rss'
const sourceType = ref<SourceType>('local')
const wordpress = ref({ siteUrl: '', apiKey: '' })
const rssFeeds = ref<string[]>([''])

const normalizeUrl = (url: string): string =>
  /^https?:\/\//i.test(url) ? url : `https://${url}`

const addRssFeed = () => {
  rssFeeds.value.push('')
}

const removeRssFeed = (index: number) => {
  rssFeeds.value.splice(index, 1)
}

const tagInput = ref('')
const fileDescriptions = ref<Record<string, string>>({})
const { getFileIcon, getFileIconColor } = useFileIcon()
const fileExplorerRef = ref<InstanceType<typeof FileExplorer> | null>(null)
const isCreating = ref(false)
const isInitialized = ref(false)

// Computed properties
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const isFormValid = computed(() => {
  if (isCreating.value) return false

  // For editing mode, only name is required
  if (props.dataset) {
    return formData.value.name.trim() !== ''
  }

  // For creation mode, name plus the fields relevant to the chosen source type
  if (formData.value.name.trim() === '') return false

  if (sourceType.value === 'wordpress') {
    return wordpress.value.siteUrl.trim() !== '' && wordpress.value.apiKey.trim() !== ''
  }

  if (sourceType.value === 'rss') {
    return rssFeeds.value.some((feed) => feed.trim() !== '')
  }

  return formData.value.selectedFiles.length > 0
})

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

  // RSS connector is illustrative (UI only) — no backend call.
  if (!props.dataset && sourceType.value === 'rss') {
    toast.success(`RSS connector "${formData.value.name.trim()}" added`)
    emit('dataset-created')
    resetForm()
    isOpen.value = false
    return
  }

  isCreating.value = true

  try {
    // Transform file paths to array of objects with path and description
    const filePathsWithDescriptions = formData.value.selectedFiles.map((filePath) => ({
      path: filePath,
      description: fileDescriptions.value[filePath] || '',
    }))

    if (props.dataset) {
      // Update existing dataset (backend only supports name, summary, tags)
      const updateRequest: UpdateDatasetRequest = {
        name: formData.value.name.trim(),
        summary: formData.value.summary.trim() || '',
        tags: formData.value.tags.join(','),
      }

      await datasetsApi.update(props.dataset.name, updateRequest)
      emit('dataset-updated')
      toast.success(`"${props.dataset.name}" updated`)
    } else if (sourceType.value === 'wordpress') {
      // WordPress connectors persist as a real dataset entry so they show up
      // alongside local sources. Registered as a remote type (no local
      // provisioner to spin up) with the site as a stub connection.
      const siteUrl = normalizeUrl(wordpress.value.siteUrl.trim())
      const tags = [...formData.value.tags]
      if (!tags.includes('wordpress')) tags.push('wordpress')

      const createRequest: CreateDatasetRequest = {
        dtype: 'remote_weaviate',
        name: formData.value.name.trim(),
        summary: formData.value.summary.trim() || `WordPress connector — ${siteUrl}`,
        tags: tags.join(','),
        configuration: {
          http_url: siteUrl,
          grpc_url: siteUrl,
          api_key: wordpress.value.apiKey.trim(),
          collection_name: formData.value.name.trim(),
        },
      }

      await datasetsApi.create(createRequest)
      emit('dataset-created')
      toast.success(`"${createRequest.name}" added`)
    } else {
      // Create new local dataset
      const createRequest: CreateDatasetRequest = {
        dtype: 'local_file',
        name: formData.value.name.trim(),
        summary: formData.value.summary.trim() || '',
        tags: formData.value.tags.join(','),
        configuration: {
          filePaths: filePathsWithDescriptions,
        },
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
  sourceType.value = 'local'
  wordpress.value = { siteUrl: '', apiKey: '' }
  rssFeeds.value = ['']
  tagInput.value = ''
  fileDescriptions.value = {}
  isInitialized.value = false
}

// Initialize form data when dialog opens with dataset (for editing)
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
