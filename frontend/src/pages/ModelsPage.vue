<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Brain class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Your Models</h1>
      </div>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Models here are accessible only for your private use. They're ideal for building powerful
        flows on your machine; expose them to others later by creating endpoints.
      </p>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center justify-between mb-8">
      <div class="relative w-64">
        <Search
          class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground"
        />
        <Input
          v-model="searchQuery"
          placeholder="Search models..."
          class="pl-10 pr-4 py-2.5 w-full"
        />
      </div>
      <Button @click="showCreateModelDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Model
      </Button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex justify-center items-center py-12">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p class="text-muted-foreground">Loading models...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-destructive/10 border border-destructive/20 rounded-lg p-6 text-center">
      <p class="text-destructive mb-4">{{ error }}</p>
      <Button @click="fetchModels" variant="outline">
        Try Again
      </Button>
    </div>

    <!-- Empty State (when no models exist) -->
    <div v-else-if="models.length === 0" class="bg-card rounded-lg shadow border border-border p-8 text-center">
      <Brain class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">No models yet</h3>
      <p class="text-muted-foreground mb-4">Start by adding or connecting your first AI model</p>
      <Button @click="showCreateModelDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Model
      </Button>
    </div>

    <!-- Models List -->
    <div v-else class="space-y-5">
      <div
        v-for="model in filteredModels"
        :key="model.id"
        class="bg-card border border-border rounded-xl p-6 hover:shadow-lg transition-all cursor-pointer"
        @click="navigateToDetail(model.name)"
      >
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div class="p-3.5 rounded-xl bg-primary/10">
              <IntegrationIcon :name="model.dtype" context="models" class="h-6 w-6" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-2">
                <h3 class="heading-4 text-foreground">{{ model.name }}</h3>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Badge
                        variant="outline"
                        :class="
                          model.endpointCount > 0
                            ? 'bg-primary/10 text-primary border border-primary/20 cursor-help'
                            : 'bg-muted text-muted-foreground border border-border'
                        "
                        class="body-sm px-2.5 py-1 rounded-md"
                      >
                        <div
                          :class="
                            model.endpointCount > 0
                              ? 'w-2 h-2 bg-secondary rounded-full mr-1'
                              : 'w-2 h-2 bg-muted-foreground rounded-full mr-1'
                          "
                        ></div>
                        {{
                          model.endpointCount === 0
                            ? 'No endpoints'
                            : `${model.endpointCount} endpoint${model.endpointCount !== 1 ? 's' : ''}`
                        }}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent v-if="model.endpointCount > 0">
                      <div class="space-y-1">
                        <p class="font-medium body-sm">Connected Endpoints:</p>
                        <ul class="space-y-1">
                          <li
                            v-for="endpointName in getEndpointNamesForModel(model.id)"
                            :key="endpointName"
                            class="body-sm"
                          >
                            • {{ endpointName }}
                          </li>
                        </ul>
                      </div>
                    </TooltipContent>
                    <TooltipContent v-else>
                      <p class="body-sm">This model is not connected to any endpoint</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p class="body-sm text-muted-foreground mb-4">
                {{ model.summary }}
              </p>
              <div v-if="model.tags" class="flex gap-2">
                <Badge v-for="tag in model.tags.split(',').filter(t => t.trim())" :key="tag" variant="outline" class="body-sm">
                  {{ tag.trim() }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              class="text-destructive hover:text-destructive"
              @click.stop="handleDeleteModel(model)"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Create Model Dialog -->
  <CreateModelDialogSimple
    v-model:open="showCreateModelDialog"
    @model-created="handleModelCreated"
    @model-updated="handleModelUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Delete Model</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ modelToDelete?.name }}"? This action cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <div v-if="modelToDelete && modelToDelete.endpointCount > 0" class="py-4">
        <div class="space-y-4">
          <div class="bg-destructive/10 border border-destructive/20 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-destructive font-semibold body-sm mb-2">
                  This model has {{ modelToDelete.endpointCount }} dependent endpoint{{
                    modelToDelete.endpointCount !== 1 ? 's' : ''
                  }}
                  that will be deleted:
                </p>
                <p class="text-destructive/80 body-sm mb-3">
                  Check each endpoint to confirm deletion
                </p>
                <div class="space-y-2">
                  <div
                    v-for="endpointName in getEndpointNamesForModel(modelToDelete.id)"
                    :key="endpointName"
                    class="flex items-center gap-3 p-2.5 bg-background rounded border border-destructive/20"
                  >
                    <input
                      type="checkbox"
                      :id="`endpoint-${endpointName}`"
                      :checked="checkedEndpoints.includes(endpointName)"
                      @change="() => toggleEndpoint(endpointName)"
                      class="w-4 h-4 text-destructive bg-background border-destructive rounded focus:ring-destructive focus:ring-2"
                    />
                    <label
                      :for="`endpoint-${endpointName}`"
                      class="flex-1 cursor-pointer flex items-center justify-between"
                    >
                      <span class="body-sm font-medium text-foreground">
                        {{ endpointName }}
                      </span>
                      <span class="body-sm text-destructive"> Will be deleted </span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="cancelDeleteModel"> Cancel </Button>
        <Button variant="destructive" @click="confirmDeleteModel" :disabled="!allEndpointsChecked">
          {{
            modelToDelete && modelToDelete.endpointCount && modelToDelete.endpointCount > 0
              ? `Delete Model & ${modelToDelete.endpointCount} Endpoint${modelToDelete.endpointCount !== 1 ? 's' : ''}`
              : 'Delete Model'
          }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Brain, Plus, Trash2, Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialogSimple from '@/components/CreateModelDialogSimple.vue'
import { modelsApi } from '@/api/endpoints/models'
import type { ModelListItem } from '@/api/types'
import { toast } from 'vue-sonner'

// Extended interface for UI-specific properties
interface ModelWithUI extends ModelListItem {
  endpointCount: number // Mock endpoint count
}

interface Endpoint {
  id: string
  name: string
  modelIds: string[]
}

// Mock endpoints data (temporary until endpoints API is integrated)
const mockEndpoints: Endpoint[] = [
  {
    id: 'endpoint-1',
    name: 'Document Analysis API',
    modelIds: ['nlp-engine'],
  },
  {
    id: 'endpoint-2',
    name: 'Content Generation API',
    modelIds: ['nlp-engine'],
  },
  {
    id: 'endpoint-3',
    name: 'Code Review Assistant',
    modelIds: ['code-assistant'],
  },
]

const router = useRouter()

// API data state
const models = ref<ModelWithUI[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

const showCreateModelDialog = ref(false)
const searchQuery = ref('')
const showDeleteDialog = ref(false)
const modelToDelete = ref<ModelWithUI | null>(null)
const checkedEndpoints = ref<string[]>([])

// Fetch models on component mount
onMounted(async () => {
  await fetchModels()
})

// Fetch models from API
const fetchModels = async () => {
  isLoading.value = true
  error.value = null
  
  try {
    const response = await modelsApi.list()
    // Transform API response to include UI-specific properties
    models.value = response.map(model => ({
      ...model,
      endpointCount: mockEndpoints.filter(e => e.modelIds.includes(model.id)).length
    }))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load models'
    toast.error('Failed to load models')
    console.error('Failed to fetch models:', err)
  } finally {
    isLoading.value = false
  }
}

const filteredModels = computed(() => {
  return models.value.filter((model) => {
    // Search query filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      if (
        !model.name.toLowerCase().includes(query) &&
        !model.summary.toLowerCase().includes(query) &&
        !model.tags.toLowerCase().includes(query)
      ) {
        return false
      }
    }

    return true
  })
})

const handleModelCreated = async () => {
  console.log('Model created successfully')
  await fetchModels() // Refresh the list
}

const handleModelUpdated = async () => {
  console.log('Model updated successfully')
  await fetchModels() // Refresh the list
}

// Function to get endpoint names connected to a model
const getEndpointNamesForModel = (modelId: string): string[] => {
  return mockEndpoints
    .filter((endpoint) => endpoint.modelIds.includes(modelId))
    .map((endpoint) => endpoint.name)
}

// Reset state when dialog closes
const handleDialogClose = () => {
  // Nothing to reset for now
}

const handleDeleteModel = (model: ModelWithUI) => {
  modelToDelete.value = model
  checkedEndpoints.value = []
  showDeleteDialog.value = true
}

const confirmDeleteModel = async () => {
  if (modelToDelete.value) {
    try {
      await modelsApi.delete(modelToDelete.value.name)
      toast.success(`Model "${modelToDelete.value.name}" deleted successfully`)
      await fetchModels() // Refresh the list
      showDeleteDialog.value = false
      modelToDelete.value = null
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete model'
      toast.error(errorMessage)
      console.error('Failed to delete model:', err)
    }
  }
}

const cancelDeleteModel = () => {
  showDeleteDialog.value = false
  modelToDelete.value = null
  checkedEndpoints.value = []
}

// Check if all endpoints are selected
const allEndpointsChecked = computed(() => {
  if (!modelToDelete.value) return true
  if (modelToDelete.value.endpointCount === 0) return true

  const endpointNames = getEndpointNamesForModel(modelToDelete.value.id)
  return endpointNames.length > 0 && endpointNames.length === checkedEndpoints.value.length
})

// Navigate to model detail page
const navigateToDetail = (modelSlug: string) => {
  router.push(`/models/${modelSlug}`)
}

// Toggle endpoint checkbox
const toggleEndpoint = (endpointName: string) => {
  const index = checkedEndpoints.value.indexOf(endpointName)
  if (index > -1) {
    checkedEndpoints.value.splice(index, 1)
  } else {
    checkedEndpoints.value.push(endpointName)
  }
}
</script>
