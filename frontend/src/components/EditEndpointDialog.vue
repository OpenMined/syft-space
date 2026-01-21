<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[600px] max-h-[90vh] flex flex-col">
      <DialogHeader>
        <DialogTitle>Edit endpoint</DialogTitle>
        <DialogDescription> Update the endpoint summary and description. </DialogDescription>
      </DialogHeader>
      <div class="space-y-4 py-4 overflow-y-auto flex-1 -mr-6 pr-6">
        <div class="space-y-2">
          <Label class="body-sm font-medium text-foreground">Name</Label>
          <Input :model-value="endpoint?.name || ''" disabled class="w-full font-mono body-sm bg-muted" />
          <p class="body-sm text-muted-foreground">Name cannot be changed after creation</p>
        </div>
        <div class="space-y-2">
          <Label for="edit-summary" class="body-sm font-medium text-foreground">
            Short Description <span class="text-red-500">*</span>
          </Label>
          <Input
            id="edit-summary"
            v-model="localSummary"
            :placeholder="endpoint?.summary || ''"
            class="w-full"
          />
          <p class="body-sm text-muted-foreground">
            This appears when people browse available content
          </p>
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <Label for="edit-description" class="body-sm font-medium text-foreground">
              More details (optional)
            </Label>
            <Button
              variant="ghost"
              size="sm"
              class="h-8 px-2"
              @click="isPreviewMode = !isPreviewMode"
            >
              <Eye v-if="!isPreviewMode" class="h-4 w-4 mr-1" />
              <Pencil v-else class="h-4 w-4 mr-1" />
              {{ isPreviewMode ? 'Edit' : 'Preview' }}
            </Button>
          </div>
          <MdPreview
            v-if="isPreviewMode"
            :model-value="localDescription || '*No content*'"
            :theme="isDark ? 'dark' : 'light'"
            class="border rounded-md min-h-[200px]"
          />
          <MdEditor
            v-else
            v-model="localDescription"
            :height="200"
            :theme="isDark ? 'dark' : 'light'"
            :preview="false"
            :toolbars="[
              'bold',
              'italic',
              'title',
              'strikeThrough',
              'unorderedList',
              'orderedList',
              'link',
              'code',
              'codeRow',
            ]"
            :preview-theme="'github'"
            :code-theme="'github'"
            language="en-US"
          />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="handleCancel" :disabled="isSaving">Cancel</Button>
        <Button @click="handleSave" :disabled="isSaving || !localSummary.trim()">
          <div v-if="isSaving" class="flex items-center gap-2">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            Saving...
          </div>
          <span v-else>Save Changes</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Eye, Pencil } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useTheme } from '@/composables/useTheme'
import { endpointsApi } from '@/api/endpoints/endpoints'

interface EndpointData {
  slug: string
  name: string
  summary: string
  description?: string
}

const props = defineProps<{
  open: boolean
  endpoint: EndpointData | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: [data: { summary: string; description: string }]
}>()

const { isDark } = useTheme()

const localSummary = ref('')
const localDescription = ref('')
const isSaving = ref(false)
const isPreviewMode = ref(false)

// Watch for endpoint changes to initialize form
watch(
  () => props.endpoint,
  async (newEndpoint) => {
    if (newEndpoint) {
      localSummary.value = newEndpoint.summary
      localDescription.value = newEndpoint.description || ''
      isPreviewMode.value = false

      // Fetch full endpoint details to get description if not provided
      if (!newEndpoint.description) {
        try {
          const fullEndpoint = await endpointsApi.get(newEndpoint.slug)
          if (fullEndpoint.description) {
            localDescription.value = fullEndpoint.description
          }
        } catch (error) {
          console.error('Failed to fetch endpoint details:', error)
        }
      }
    }
  },
  { immediate: true }
)

// Reset when dialog closes
watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      isPreviewMode.value = false
    }
  }
)

const handleCancel = () => {
  emit('update:open', false)
}

const handleSave = async () => {
  if (!props.endpoint || isSaving.value) return

  isSaving.value = true

  try {
    // Call the update API
    await endpointsApi.update(props.endpoint.slug, {
      summary: localSummary.value,
      description: localDescription.value || undefined,
    })

    // Publish the endpoint to sync changes with SyftHub
    await endpointsApi.publish(props.endpoint.slug, {
      publish_to_all_marketplaces: true,
    })

    // Emit saved event with the new data
    emit('saved', {
      summary: localSummary.value,
      description: localDescription.value,
    })

    emit('update:open', false)
  } catch (error) {
    console.error('Failed to update endpoint:', error)
  } finally {
    isSaving.value = false
  }
}
</script>
