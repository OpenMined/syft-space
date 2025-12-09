<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">Create Model</DialogTitle>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Model Name -->
        <div class="space-y-2">
          <Label for="model-name" class="text-sm font-medium">
            Model Name <span class="text-red-500">*</span>
          </Label>
          <Input id="model-name" v-model="formData.name" placeholder="e.g., Legal AI Assistant" class="w-full" />
          <p class="text-sm text-muted-foreground">
            Give your model a descriptive name
          </p>
        </div>

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
              <SelectItem value="openrouter">OpenRouter</SelectItem>
            </SelectContent>
          </Select>
          <p class="text-sm text-muted-foreground">
            Choose your AI model provider
          </p>
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
              <SelectItem v-for="model in availableModels" :key="model.value" :value="model.value">
                {{ model.label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-sm text-muted-foreground">
            Select the specific model to use
          </p>
        </div>

        <!-- API Key -->
        <div class="space-y-2">
          <Label for="api-key" class="text-sm font-medium">
            API Key <span class="text-red-500">*</span>
          </Label>
          <Input id="api-key" v-model="formData.apiKey" type="password" placeholder="Enter your API key"
            class="w-full" />
          <p class="text-sm text-muted-foreground">
            Your API key for authentication
          </p>
        </div>

        <!-- Summary -->
        <div class="space-y-2">
          <Label for="summary" class="text-sm font-medium">
            Summary (Optional)
          </Label>
          <Input id="summary" v-model="formData.summary"
            placeholder="Describe what this model does and how it can be used..." class="w-full" />
          <p class="text-sm text-muted-foreground">
            A brief description of your model's capabilities
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
            Tags help others discover your model
          </p>
        </div>
      </div>

      <DialogFooter class="mt-8">
        <Button variant="outline" @click="handleCancel">
          Cancel
        </Button>
        <Button @click="handleCreate" :disabled="!isFormValid">
          Create Model
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

interface Model {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
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
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
]

const openrouterModels = [
  { value: 'meta-llama/llama-3.2-90b-vision-instruct', label: 'Llama 3.2 90B Vision' },
  { value: 'google/gemini-2.0-flash-exp:free', label: 'Gemini 2.0 Flash' },
  { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek Chat' },
  { value: 'mistralai/mistral-large', label: 'Mistral Large' },
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
  if (formData.value.provider === 'openai') {
    return openaiModels
  } else if (formData.value.provider === 'openrouter') {
    return openrouterModels
  }
  return []
})

const isFormValid = computed(() => {
  return (
    formData.value.name.trim() !== '' &&
    formData.value.provider !== '' &&
    formData.value.model !== '' &&
    formData.value.apiKey.trim() !== ''
  )
})

// Watch for provider changes to reset model selection
watch(() => formData.value.provider, () => {
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

const handleCreate = () => {
  if (!isFormValid.value) return

  const modelName = formData.value.name

  // Emit create event
  if (props.model) {
    emit('model-updated')
    toast.success(`Model "${modelName}" updated successfully`)
  } else {
    emit('model-created')
    toast.success(`Model "${modelName}" created successfully`)
  }

  resetForm()
  isOpen.value = false
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

// Initialize form data if editing
if (props.model) {
  formData.value.name = props.model.name
  formData.value.tags = [...props.model.tags]
}
</script>