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

        <!-- Provider and Model Side by Side (only show when creating) -->
        <div v-if="!props.model" class="grid grid-cols-2 gap-4">
          <!-- Provider -->
          <div class="space-y-2">
            <Label for="provider" class="text-sm font-medium">
              Provider <span class="text-red-500">*</span>
            </Label>
            <Select v-model="formData.provider">
              <SelectTrigger id="provider" class="w-full">
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="groq">Groq</SelectItem>
                <SelectItem value="openrouter">OpenRouter</SelectItem>
                <SelectItem value="together">Together AI</SelectItem>
                <SelectItem value="perplexity">Perplexity</SelectItem>
              </SelectContent>
            </Select>
            <p class="text-sm text-muted-foreground">Choose your AI model provider</p>
          </div>

          <!-- Model -->
          <div class="space-y-2">
            <Label for="model" class="text-sm font-medium">
              Model <span class="text-red-500">*</span>
            </Label>
            <Select v-model="formData.model" :disabled="!formData.provider">
              <SelectTrigger id="model" class="w-full">
                <SelectValue placeholder="Select a model" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="model in availableModels"
                  :key="model.value"
                  :value="model.value"
                >
                  {{ model.label }}
                </SelectItem>
              </SelectContent>
            </Select>
            <p class="text-sm text-muted-foreground">Select the specific model to use</p>
          </div>
        </div>

        <!-- API Key (only show when creating) -->
        <div v-if="!props.model" class="space-y-2">
          <Label for="api-key" class="text-sm font-medium">
            {{ apiKeyLabel }} <span class="text-red-500">*</span>
          </Label>
          <Input
            id="api-key"
            v-model="formData.apiKey"
            type="password"
            :placeholder="apiKeyPlaceholder"
            class="w-full"
          />
          <p class="text-sm text-muted-foreground">Your API key for authentication</p>
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
import { Plus, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { modelsApi } from '@/api/endpoints/models'
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

// Model options for different providers
const openaiModels = [
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  { value: 'o1-preview', label: 'o1 Preview' },
  { value: 'o1-mini', label: 'o1 Mini' },
  { value: 'gpt-4-turbo-preview', label: 'GPT-4 Turbo Preview' },
]

const groqModels = [
  { value: 'llama-3.3-70b-instruct', label: 'Llama 3.3 70B Instruct' },
  { value: 'llama-3.2-90b-vision-instruct', label: 'Llama 3.2 90B Vision' },
  { value: 'llama-3.2-11b-vision-instruct', label: 'Llama 3.2 11B Vision' },
  { value: 'llama-3.1-70b-instruct', label: 'Llama 3.1 70B Instruct' },
  { value: 'llama-3.1-8b-instruct', label: 'Llama 3.1 8B Instruct' },
  { value: 'mixtral-8x7b-instruct', label: 'Mixtral 8x7B Instruct' },
  { value: 'gemma2-9b-it', label: 'Gemma 2 9B IT' },
  { value: 'gemma-7b-it', label: 'Gemma 7B IT' },
]

const openrouterModels = [
  { value: 'openai/gpt-4o', label: 'GPT-4o' },
  { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  { value: 'anthropic/claude-3-opus', label: 'Claude 3 Opus' },
  { value: 'meta-llama/llama-3.2-90b-vision-instruct', label: 'Llama 3.2 90B Vision' },
  { value: 'google/gemini-2.0-flash-exp:free', label: 'Gemini 2.0 Flash (Free)' },
  { value: 'google/gemini-pro-1.5', label: 'Gemini Pro 1.5' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek Chat' },
  { value: 'mistralai/mistral-large', label: 'Mistral Large' },
  { value: 'mistralai/codestral', label: 'Codestral' },
  { value: 'qwen/qwen-2.5-72b-instruct', label: 'Qwen 2.5 72B' },
]

const togetherModels = [
  { value: 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo', label: 'Llama 3.1 405B Turbo' },
  { value: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo', label: 'Llama 3.1 70B Turbo' },
  { value: 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo', label: 'Llama 3.1 8B Turbo' },
  { value: 'meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo', label: 'Llama 3.2 90B Vision Turbo' },
  { value: 'mistralai/Mixtral-8x22B-Instruct', label: 'Mixtral 8x22B Instruct' },
  { value: 'mistralai/Mixtral-8x7B-Instruct', label: 'Mixtral 8x7B Instruct' },
  { value: 'deepseek-ai/deepseek-coder-33b-instruct', label: 'DeepSeek Coder 33B' },
  { value: 'Qwen/Qwen2.5-72B-Instruct', label: 'Qwen 2.5 72B Instruct' },
  { value: 'Qwen/Qwen2.5-Coder-32B-Instruct', label: 'Qwen 2.5 Coder 32B' },
]

const perplexityModels = [
  { value: 'llama-3.1-sonar-huge-128k-online', label: 'Sonar Huge 128k (Online)' },
  { value: 'llama-3.1-sonar-large-128k-online', label: 'Sonar Large 128k (Online)' },
  { value: 'llama-3.1-sonar-small-128k-online', label: 'Sonar Small 128k (Online)' },
  { value: 'llama-3.1-sonar-large-128k', label: 'Sonar Large 128k' },
  { value: 'llama-3.1-sonar-small-128k', label: 'Sonar Small 128k' },
  { value: 'llama-3.1-8b-instruct', label: 'Llama 3.1 8B Instruct' },
  { value: 'llama-3.1-70b-instruct', label: 'Llama 3.1 70B Instruct' },
]

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

// Computed properties
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const availableModels = computed(() => {
  switch (formData.value.provider) {
    case 'openai':
      return openaiModels
    case 'groq':
      return groqModels
    case 'openrouter':
      return openrouterModels
    case 'together':
      return togetherModels
    case 'perplexity':
      return perplexityModels
    default:
      return []
  }
})

// API Key label based on selected provider
const apiKeyLabel = computed(() => {
  const providerNames = {
    openai: 'OpenAI',
    groq: 'Groq',
    openrouter: 'OpenRouter',
    together: 'Together AI',
    perplexity: 'Perplexity',
  }

  const providerName = providerNames[formData.value.provider as keyof typeof providerNames]
  return providerName ? `${providerName} API Key` : 'API Key'
})

// API Key placeholder based on selected provider
const apiKeyPlaceholder = computed(() => {
  const providerNames = {
    openai: 'OpenAI',
    groq: 'Groq',
    openrouter: 'OpenRouter',
    together: 'Together AI',
    perplexity: 'Perplexity',
  }

  const providerName = providerNames[formData.value.provider as keyof typeof providerNames]
  return providerName ? `Enter your ${providerName} API key` : 'Enter your API key'
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

// Watch for provider changes to reset model selection
watch(
  () => formData.value.provider,
  () => {
    formData.value.model = ''
  },
)

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
      const getBaseUrl = (provider: string) => {
        switch (provider) {
          case 'openai':
            return 'https://api.openai.com/v1'
          case 'groq':
            return 'https://api.groq.com/openai/v1'
          case 'openrouter':
            return 'https://openrouter.ai/api/v1'
          case 'together':
            return 'https://api.together.xyz/v1'
          case 'perplexity':
            return 'https://api.perplexity.ai'
          default:
            return 'https://api.openai.com/v1'
        }
      }

      const createRequest: CreateModelRequest = {
        name: formData.value.name,
        dtype: 'openai',
        configuration: {
          api_key: formData.value.apiKey,
          model: formData.value.model,
          base_url: getBaseUrl(formData.value.provider),
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
