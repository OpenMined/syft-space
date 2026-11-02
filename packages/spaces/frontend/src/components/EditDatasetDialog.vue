<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[640px] max-h-[90vh] flex flex-col">
      <DialogHeader>
        <DialogTitle class="heading-3">Edit Data Source</DialogTitle>
        <DialogDescription v-if="dataset"> {{ typeLabel }} · {{ dataset.name }} </DialogDescription>
      </DialogHeader>

      <div class="space-y-6 mt-4 flex-1 overflow-y-auto min-h-0 -mx-1 px-1">
        <div class="space-y-2">
          <Label for="edit-dataset-name" class="text-sm font-medium">
            Name <span class="text-red-500">*</span>
          </Label>
          <Input id="edit-dataset-name" v-model="name" class="w-full" />
        </div>

        <div class="space-y-2">
          <Label for="edit-dataset-summary" class="text-sm font-medium">Summary</Label>
          <Input
            id="edit-dataset-summary"
            v-model="summary"
            placeholder="What does this data source contain?"
            class="w-full"
          />
        </div>

        <div class="space-y-2">
          <Label for="edit-dataset-tags" class="text-sm font-medium">Tags</Label>
          <TagsInput id="edit-dataset-tags" v-model="tags" />
        </div>

        <!-- Configuration: only what the type lets an owner change. -->
        <template v-if="editor.loading.value">
          <Skeleton class="h-9 w-full" />
          <Skeleton class="h-9 w-full" />
        </template>
        <p v-else-if="editor.loadError.value" class="text-xs text-destructive">
          {{ editor.loadError.value }}
        </p>
        <template v-else-if="editor.fields.value.length > 0">
          <Separator />
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-medium">Configuration</h3>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 text-xs"
              :disabled="!editor.isValid.value || editor.testing.value"
              @click="editor.testConnection(dataset!.name)"
            >
              <Loader2 v-if="editor.testing.value" class="h-3.5 w-3.5 mr-1.5 animate-spin" />
              <Activity v-else class="h-3.5 w-3.5 mr-1.5" />
              Test connection
            </Button>
          </div>

          <DatasetConfigFields
            :groups="editor.groups.value"
            :drafts="editor.drafts.value"
            :errors="editor.errors.value"
            @update="editor.setDraft"
          />

          <Alert
            v-if="editor.health.value"
            :variant="editor.health.value.status === 'healthy' ? 'default' : 'destructive'"
          >
            <CheckCircle2 v-if="editor.health.value.status === 'healthy'" class="h-4 w-4" />
            <AlertCircle v-else class="h-4 w-4" />
            <AlertTitle>
              {{
                editor.health.value.status === 'healthy' ? 'Connection works' : 'Connection failed'
              }}
            </AlertTitle>
            <AlertDescription v-if="editor.health.value.message">
              {{ editor.health.value.message }}
            </AlertDescription>
          </Alert>
        </template>

        <Alert v-if="editor.serverError.value" variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertDescription>{{ editor.serverError.value }}</AlertDescription>
        </Alert>
      </div>

      <DialogFooter class="mt-6 flex-shrink-0">
        <Button variant="outline" @click="handleCancel">Cancel</Button>
        <Button :disabled="!canSave" @click="handleSave">
          <Loader2 v-if="isSaving" class="h-3.5 w-3.5 mr-1.5 animate-spin" />
          {{ saveLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Activity, AlertCircle, CheckCircle2, Loader2 } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import TagsInput from '@/components/TagsInput.vue'
import DatasetConfigFields from '@/components/DatasetConfigFields.vue'
import { useDatasetConfigEditor } from '@/composables/useDatasetConfigEditor'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { DatasetResponse, UpdateDatasetRequest } from '@/api/types'
import { sourcePresentation } from '@/config/sources'
import { apiErrorMessage } from '@/lib/apiError'
import { toast } from 'vue-sonner'

export interface EditableDataset {
  name: string
  dtype: string
  summary: string
  tags: string[]
  configuration: Record<string, unknown>
}

const props = defineProps<{
  open: boolean
  dataset: EditableDataset | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  // `configurationChanged` tells the owner page a republish may be due.
  'dataset-updated': [dataset: DatasetResponse, configurationChanged: boolean]
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const name = ref('')
const summary = ref('')
const tags = ref<string[]>([])
const isSaving = ref(false)
const editor = useDatasetConfigEditor()

const typeLabel = computed(() =>
  props.dataset ? sourcePresentation(props.dataset.dtype).label : '',
)

const canSave = computed(
  () =>
    !isSaving.value && !editor.loading.value && name.value.trim() !== '' && editor.isValid.value,
)

// A configuration edit is validated server-side before it is written;
// a metadata-only edit is just written.
const saveLabel = computed(() => {
  if (!isSaving.value) return 'Save Changes'
  return editor.hasChanges.value ? 'Validating & saving...' : 'Saving...'
})

const handleCancel = () => {
  isOpen.value = false
}

const handleSave = async () => {
  if (!props.dataset || !canSave.value) return
  isSaving.value = true
  editor.serverError.value = null
  try {
    const request: UpdateDatasetRequest = {
      name: name.value.trim(),
      summary: summary.value.trim(),
      tags: tags.value.join(','),
    }
    const configurationChanged = editor.hasChanges.value
    if (configurationChanged) request.configuration = editor.patch.value

    const updated = await datasetsApi.update(props.dataset.name, request)
    toast.success(`"${updated.name}" updated`)
    emit('dataset-updated', updated, configurationChanged)
    isOpen.value = false
  } catch (err) {
    editor.serverError.value = apiErrorMessage(err, 'Failed to save data source')
  } finally {
    isSaving.value = false
  }
}

watch(
  () => [props.open, props.dataset] as const,
  async ([open, dataset]) => {
    if (!open || !dataset) {
      editor.reset()
      return
    }
    name.value = dataset.name
    summary.value = dataset.summary ?? ''
    tags.value = [...dataset.tags]
    await editor.load(dataset.dtype, dataset.configuration)
  },
  { immediate: true },
)
</script>
