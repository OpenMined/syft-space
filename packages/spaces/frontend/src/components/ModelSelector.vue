<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="space-y-2">
      <h4 class="text-base font-medium text-foreground">{{ title }}</h4>
      <p class="text-sm text-muted-foreground">{{ description }}</p>
    </div>

    <!-- Model List -->
    <RadioGroup :model-value="modelValue" @update:model-value="handleModelValueUpdate">
      <div class="space-y-3">
        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-8">
          <div class="text-center">
            <div
              class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"
            ></div>
            <p class="text-sm text-muted-foreground">Loading models...</p>
          </div>
        </div>

        <!-- Error State -->
        <div
          v-else-if="error"
          class="bg-destructive/10 border border-destructive/20 rounded-lg p-4 text-center"
        >
          <p class="text-sm text-destructive">{{ error }}</p>
        </div>

        <!-- Existing Models -->
        <div
          v-else
          v-for="model in models"
          :key="model.id"
          class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-primary/5 dark:hover:bg-primary/10"
          :class="
            modelValue === model.id
              ? 'border-primary bg-primary/5 dark:bg-primary/10'
              : 'border-border'
          "
          @click="$emit('update:modelValue', model.id)"
        >
          <RadioGroupItem :value="model.id" :id="`${idPrefix}-${model.id}`" />
          <Label
            :for="`${idPrefix}-${model.id}`"
            class="flex items-center gap-3 cursor-pointer flex-1"
          >
            <div class="p-2 rounded bg-primary/10">
              <IntegrationIcon :name="model.dtype" context="models" class="h-5 w-5" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ model.name }}</span>
                <Badge variant="secondary" class="text-xs">{{ model.dtype }}</Badge>
                <Badge
                  variant="outline"
                  :class="
                    model.status === 'running'
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-muted text-muted-foreground border-border'
                  "
                  class="text-xs"
                >
                  {{ model.status }}
                </Badge>
              </div>
              <p class="text-sm text-muted-foreground mt-1">{{ model.summary }}</p>
            </div>
          </Label>
        </div>

        <!-- Create New Model Option -->
        <button
          class="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mt-1 ml-1"
          @click="handleCreateModel"
        >
          <Plus class="h-3.5 w-3.5" />
          Add a new model
        </button>
      </div>
    </RadioGroup>
  </div>

  <!-- Create Model Dialog -->
  <CreateModelDialogSimple
    v-model:open="showCreateModelDialog"
    @model-created="handleModelCreated"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialogSimple from '@/components/CreateModelDialogSimple.vue'
import { modelsApi } from '@/api/endpoints/models'
import type { ModelListItem } from '@/api/types'

// Extended interface for UI-specific properties
interface ModelWithStatus extends ModelListItem {
  status: 'running' | 'stopped'
}

interface Props {
  modelValue: string
  title?: string
  description?: string
  idPrefix?: string
}

withDefaults(defineProps<Props>(), {
  title: 'AI Model',
  description: 'Select an AI model',
  idPrefix: 'model',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'create-model': []
}>()

// State for fetching models
const models = ref<ModelWithStatus[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

// Dialog state
const showCreateModelDialog = ref(false)

// Fetch models from API
const fetchModels = async () => {
  isLoading.value = true
  error.value = null

  try {
    const response = await modelsApi.list()
    // Transform API response to include status (defaulting to 'running' for active models)
    models.value = response.map((model) => ({
      ...model,
      status: 'running' as const, // Assume running models for now, can be enhanced later with actual status
    }))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load models'
    console.error('Failed to fetch models:', err)
    // Fallback to empty array on error
    models.value = []
  } finally {
    isLoading.value = false
  }
}

// Load models on component mount
onMounted(async () => {
  await fetchModels()
})

const handleCreateModel = () => {
  showCreateModelDialog.value = true
  emit('create-model')
}

const handleModelValueUpdate = (value: unknown) => {
  if (typeof value === 'string') {
    emit('update:modelValue', value)
    return
  }

  if (value === null || value === undefined) {
    emit('update:modelValue', '')
  }
}

// Handle model creation success
defineExpose({ models })

const handleModelCreated = async () => {
  console.log('Model created successfully')

  // Store the current model IDs before refresh
  const previousModelIds = new Set(models.value.map((model) => model.id))

  // Refresh the models list
  await fetchModels()

  // Find and auto-select the newly created model
  const newModel = models.value.find((model) => !previousModelIds.has(model.id))
  if (newModel) {
    emit('update:modelValue', newModel.id)
  }
}
</script>
