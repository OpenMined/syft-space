<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">{{
          props.model ? 'Edit Model' : 'Create Model'
        }}</DialogTitle>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Model Name -->
        <div class="space-y-2">
          <Label for="model-name" class="text-sm font-medium">
            Model Name <span class="text-red-500">*</span>
          </Label>
          <Input
            id="model-name"
            v-model="formData.name"
            placeholder="e.g., Legal AI Assistant"
            class="w-full"
          />
          <p class="text-sm text-muted-foreground">Give your model a descriptive name</p>
        </div>

        <!-- Provider (only show when creating) -->
        <div v-if="!props.model" class="space-y-2">
          <Label for="provider" class="text-sm font-medium">
            Provider <span class="text-red-500">*</span>
          </Label>
          <Select v-model="formData.provider">
            <SelectTrigger id="provider" class="w-full">
              <SelectValue placeholder="Select a provider" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="p in PROVIDERS" :key="p.id" :value="p.id">
                {{ p.label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-sm text-muted-foreground">Choose your AI model provider</p>
        </div>

        <!-- API Key (shown after provider is selected) -->
        <div v-if="!props.model && formData.provider" class="space-y-2">
          <Label for="api-key" class="text-sm font-medium">
            {{ getProviderLabel(formData.provider) }} API Key
            <span class="text-red-500">*</span>
          </Label>
          <Input
            id="api-key"
            v-model="formData.apiKey"
            type="password"
            :placeholder="`Enter your ${getProviderLabel(formData.provider)} API key`"
            class="w-full"
          />
          <p class="text-sm text-muted-foreground">
            Models will be fetched automatically after entering your key
          </p>
        </div>

        <!-- Model (shown after API key is entered) -->
        <div v-if="!props.model && formData.provider && formData.apiKey.trim()" class="space-y-2">
          <Label for="model" class="text-sm font-medium">
            Model <span class="text-red-500">*</span>
          </Label>
          <ProviderModelCombobox
            v-model="formData.model"
            :models="providerModels"
            :is-loading="isLoadingModels"
            :error="modelsError"
            :disabled="isLoadingModels"
            placeholder="Select a model"
          />
          <p v-if="isLoadingModels" class="text-sm text-muted-foreground">
            Fetching available models...
          </p>
          <p v-else-if="hasModelsFetched" class="text-sm text-muted-foreground">
            {{ providerModels.length }} models available
          </p>
        </div>

        <!-- Summary -->
        <div class="space-y-2">
          <Label for="summary" class="text-sm font-medium"> Summary (Optional) </Label>
          <Input
            id="summary"
            v-model="formData.summary"
            placeholder="Describe what this model does and how it can be used..."
            class="w-full"
          />
          <p class="text-sm text-muted-foreground">
            A brief description of your model's capabilities
          </p>
        </div>

        <!-- Tags -->
        <div class="space-y-2">
          <Label for="topics" class="text-sm font-medium"> Tags (Optional) </Label>
          <div class="space-y-2">
            <div class="flex gap-2">
              <Input
                id="topics"
                v-model="tagInput"
                @keydown.enter.prevent="addTag"
                placeholder="Add keywords like: legal, medical, research, finance"
                class="flex-1"
              />
              <Button @click="addTag" variant="outline" :disabled="!tagInput.trim()">
                <Plus class="h-4 w-4" />
              </Button>
            </div>
            <p class="text-sm text-muted-foreground">Tags help others discover your model</p>

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
          {{ props.model ? 'Update Model' : 'Create Model' }}
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
import ProviderModelCombobox from '@/components/ProviderModelCombobox.vue'
import { Plus, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { modelsApi } from '@/api/endpoints/models'
import { PROVIDERS, getProviderLabel, getProviderBaseUrl } from '@/config/providers'
import { useProviderModels } from '@/composables/useProviderModels'
import type { CreateModelRequest } from '@/api/types'

interface Model {
  id: string
  name: string
  summary: string
  tags: string | string[]
  dtype: string
  type?: string
  description?: string
  status?: 'running' | 'stopped'
  endpointCount?: number
  [key: string]: unknown
}

const props = defineProps<{
  open: boolean
  model?: Model | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'model-created': []
  'model-updated': []
}>()

// Popular tag suggestions
const popularTags = ['legal', 'medical', 'research', 'finance', 'coding', 'creative', 'translation']

// Form data
const formData = ref({
  name: '',
  provider: '',
  model: '',
  apiKey: '',
  summary: '',
  tags: [] as string[],
})

const tagInput = ref('')

// Provider models
const providerRef = computed(() => formData.value.provider)
const baseUrlRef = computed(() => getProviderBaseUrl(formData.value.provider))
const apiKeyRef = computed(() => formData.value.apiKey)
const {
  models: providerModels,
  isLoading: isLoadingModels,
  error: modelsError,
  hasFetched: hasModelsFetched,
} = useProviderModels(baseUrlRef, apiKeyRef)

// Computed properties
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const isFormValid = computed(() => {
  if (props.model) {
    // For editing, only name is required
    return formData.value.name.trim() !== ''
  }
  // For creating, all fields are required
  return (
    formData.value.name.trim() !== '' &&
    formData.value.provider !== '' &&
    formData.value.model !== '' &&
    formData.value.apiKey.trim() !== ''
  )
})

// Reset model selection when provider or API key changes
watch(providerRef, () => {
  formData.value.model = ''
})
watch(apiKeyRef, () => {
  formData.value.model = ''
})

// Methods
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

  const modelName = formData.value.name

  try {
    if (props.model) {
      // Update existing model
      const updateRequest = {
        name: formData.value.name,
        summary: formData.value.summary || '',
        tags: formData.value.tags.join(', '),
      }

      await modelsApi.update(props.model.name, updateRequest)
      emit('model-updated')
      toast.success(`Model "${modelName}" updated successfully`)
    } else {
      // Create new model
      const createRequest: CreateModelRequest = {
        name: formData.value.name,
        dtype: 'openai',
        configuration: {
          api_key: formData.value.apiKey,
          model: formData.value.model,
          base_url: getProviderBaseUrl(formData.value.provider),
          system_prompt: '', // Default empty system prompt
        },
        summary: formData.value.summary || '',
        tags: formData.value.tags.join(', '),
      }

      await modelsApi.create(createRequest)
      emit('model-created')
      toast.success(`Model "${modelName}" created successfully`)
    }

    resetForm()
    isOpen.value = false
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
    const action = props.model ? 'update' : 'create'
    toast.error(`Failed to ${action} model: ${errorMessage}`)
  }
}

const resetForm = () => {
  formData.value = {
    name: '',
    provider: '',
    model: '',
    apiKey: '',
    summary: '',
    tags: [],
  }
  tagInput.value = ''
}

// Watch for model prop changes to populate edit form
watch(
  () => props.model,
  (model) => {
    if (model) {
      formData.value.name = model.name
      formData.value.summary = model.summary || ''
      formData.value.tags =
        typeof model.tags === 'string'
          ? model.tags
              .split(',')
              .map((tag: string) => tag.trim())
              .filter(Boolean)
          : Array.isArray(model.tags)
            ? model.tags
            : []
      // For editing, we don't need to populate provider/model/apiKey as these are typically not editable
    } else {
      resetForm()
    }
  },
  { immediate: true },
)
</script>
