<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Header -->
    <div class="mb-12">
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Your Models</h1>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Models that live on your machine and work for you. Use endpoints to make them queryable by
        others, on your terms.
      </p>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center justify-between mb-8">
      <div class="relative w-full max-w-sm">
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
        Add
      </Button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="space-y-5">
      <div
        v-for="i in 3"
        :key="`skeleton-${i}`"
        class="bg-card border border-border rounded-xl p-6 animate-pulse"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 flex gap-4">
            <div class="w-14 h-14 bg-muted rounded-xl"></div>
            <div class="flex-1 space-y-2">
              <div class="h-6 bg-muted rounded w-1/3"></div>
              <div class="h-4 bg-muted rounded w-1/2"></div>
              <div class="h-4 bg-muted rounded w-2/3"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">Failed to load models</div>
      <Button @click="fetchModels" variant="outline">Try Again</Button>
    </div>

    <!-- Empty State -->
    <div v-else-if="models.length === 0" class="text-center py-8">
      <Brain class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">No models yet</h3>
      <p class="body-sm text-muted-foreground mb-4">
        Add your first AI model to get started
      </p>
      <Button @click="showCreateModelDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Model
      </Button>
    </div>

    <!-- Models List -->
    <div v-else class="space-y-3">
      <div
        v-for="model in filteredModels"
        :key="model.id"
        class="group rounded-lg border border-border/50 bg-card p-5 hover:shadow-sm hover:-translate-y-px transition-all cursor-pointer"
        @click="navigateToDetail(model.name)"
      >
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4 flex-1">
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
                        <Link
                          :class="
                            model.endpointCount > 0
                              ? 'w-3.5 h-3.5 mr-1.5'
                              : 'w-3.5 h-3.5 mr-1.5 opacity-40'
                          "
                        />
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
              <p class="body-sm text-muted-foreground mb-3 line-clamp-2">
                {{ model.summary }}
              </p>
              <div v-if="model.tags" class="flex gap-1.5 flex-wrap">
                <Badge
                  v-for="tag in modelTags(model.tags).slice(0, 3)"
                  :key="tag"
                  variant="secondary"
                  class="text-[11px] px-2 py-0.5"
                >
                  {{ tag }}
                </Badge>
                <span
                  v-if="modelTags(model.tags).length > 3"
                  class="text-[11px] text-muted-foreground self-center"
                >
                  +{{ modelTags(model.tags).length - 3 }}
                </span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button variant="outline" size="sm" @click.stop="handleEditModel(model)">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
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
    :model="editingModel"
    @model-created="handleModelCreated"
    @model-updated="handleModelUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <DeleteConfirmationDialog
    v-model:open="showDeleteDialog"
    item-type="Model"
    :item-name="modelToDelete?.name || ''"
    :dependencies="getEndpointNamesForModel(modelToDelete?.id || '')"
    dependency-type="endpoint"
    :is-deleting="isDeleting"
    @confirm="confirmDeleteModel"
    @cancel="cancelDeleteModel"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Brain, Plus, Trash2, Search, Edit, Link } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialogSimple from '@/components/CreateModelDialogSimple.vue'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import { modelsApi } from '@/api/endpoints/models'
import type { ModelListItem } from '@/api/types'
import { toast } from 'vue-sonner'

// Extended interface for UI-specific properties
interface ModelWithUI extends ModelListItem {
  endpointCount: number
}

const router = useRouter()

// API data state
const models = ref<ModelWithUI[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

const showCreateModelDialog = ref(false)
const searchQuery = ref('')
const editingModel = ref<ModelWithUI | null>(null)
const showDeleteDialog = ref(false)
const modelToDelete = ref<ModelWithUI | null>(null)
const isDeleting = ref(false)

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
    models.value = response.map((model) => ({
      ...model,
      endpointCount: model.connected_endpoints?.length || 0,
    }))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load models'
    toast.error('Failed to load models')
    console.error('Failed to fetch models:', err)
  } finally {
    isLoading.value = false
  }
}

const modelTags = (tags: string) =>
  tags
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)

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
  const model = models.value.find((m) => m.id === modelId)
  if (!model || !model.connected_endpoints) return []
  return model.connected_endpoints.map((endpoint) => endpoint.name)
}

const handleEditModel = async (model: ModelWithUI) => {
  try {
    const response = await modelsApi.get(model.name)
    editingModel.value = {
      ...model,
      ...response,
    }
    showCreateModelDialog.value = true
  } catch (err) {
    toast.error('Failed to load model details for editing')
    console.error('Failed to fetch model for editing:', err)
  }
}

// Reset state when dialog closes
const handleDialogClose = () => {
  editingModel.value = null
}

const handleDeleteModel = (model: ModelWithUI) => {
  modelToDelete.value = model
  showDeleteDialog.value = true
}

const confirmDeleteModel = async () => {
  if (modelToDelete.value && !isDeleting.value) {
    isDeleting.value = true
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
    isDeleting.value = false
  }
}

const cancelDeleteModel = () => {
  showDeleteDialog.value = false
  modelToDelete.value = null
}

// Navigate to model detail page
const navigateToDetail = (modelSlug: string) => {
  router.push(`/models/${modelSlug}`)
}
</script>
