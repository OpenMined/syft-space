<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-12" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-3">
        <li>
          <router-link
            to="/models"
            class="text-muted-foreground hover:text-foreground body-sm font-medium flex items-center transition-colors"
          >
            <Brain class="h-4 w-4 mr-2" />
            Models
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-muted-foreground mx-3" />
          <span class="text-foreground body-sm font-medium">{{ model?.name || 'Loading...' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-16">
      <div class="text-center">
        <div
          class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"
        ></div>
        <p class="text-muted-foreground">Loading model details...</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-destructive/10 border border-destructive/20 rounded-2xl p-8 text-center"
    >
      <h3 class="heading-3 text-destructive mb-2">Model not found</h3>
      <p class="text-destructive mb-4">
        The model you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="goToModels" variant="outline"> Back to Models </Button>
    </div>

    <!-- Model Details -->
    <div v-else-if="model" class="space-y-6">
      <!-- Header -->
      <div class="bg-card/60 backdrop-blur-sm border border-border rounded-3xl p-8 mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-6">
            <div class="p-4 rounded-2xl shadow-sm bg-primary/10 border border-border">
              <IntegrationIcon :name="model.dtype" context="models" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="heading-2 mb-2">{{ model.name }}</h1>
              <p class="body-lg text-muted-foreground mb-4">{{ model.summary }}</p>
              <div class="flex flex-wrap items-center gap-3">
                <Badge
                  variant="outline"
                  class="bg-muted text-muted-foreground border border-border px-3 py-1.5 rounded-full"
                >
                  {{ model.dtype }}
                </Badge>
                <Badge
                  v-for="tag in model.tags"
                  :key="`tag-${tag}`"
                  variant="outline"
                  class="bg-muted text-muted-foreground border border-border px-3 py-1.5 rounded-full"
                >
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Button variant="outline" @click="editModel">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              class="text-destructive hover:text-destructive border-destructive/50 hover:border-destructive"
              @click="deleteModel"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>

      <!-- Model Details Content -->
      <div class="space-y-6">
        <!-- Model Summary -->
        <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
          <div class="grid grid-cols-2 md:grid-cols-3 gap-8">
            <div class="text-center">
              <p class="body-sm text-muted-foreground mb-1">Type</p>
              <p class="body-sm font-medium text-foreground">
                {{ model.dtype }}
              </p>
            </div>

            <div class="text-center">
              <p class="body-sm text-muted-foreground mb-1">Created</p>
              <p class="body-sm font-medium text-foreground">
                {{ formatDate(new Date(model.created_at)) }}
              </p>
            </div>

            <div class="text-center">
              <p class="body-sm text-muted-foreground mb-1">Updated</p>
              <p class="body-sm font-medium text-foreground">
                {{ formatDate(new Date(model.updated_at)) }}
              </p>
            </div>
          </div>
        </div>

        <!-- Model Configuration -->
        <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
          <div class="flex items-center justify-between mb-8">
            <h2 class="heading-3">Model Configuration</h2>
          </div>

          <!-- Basic Settings -->
          <div class="space-y-6">
            <div class="flex justify-between items-center py-4 border-b border-border">
              <span class="body-sm text-muted-foreground">Base URL</span>
              <span class="body-sm font-medium text-foreground">{{
                model.configuration.base_url || 'Not configured'
              }}</span>
            </div>
            <div class="flex justify-between items-center py-4 border-b border-border">
              <span class="body-sm text-muted-foreground">Model</span>
              <span class="body-sm font-medium text-foreground">{{
                model.configuration.model || 'Not specified'
              }}</span>
            </div>
            <div class="flex justify-between items-center py-4 border-b border-border">
              <span class="body-sm text-muted-foreground">API Key</span>
              <span class="body-sm font-medium text-foreground">{{
                model.configuration.api_key ? '••••••••' : 'Not configured'
              }}</span>
            </div>
            <div
              v-if="model.configuration.system_prompt"
              class="flex justify-between items-center py-4"
            >
              <span class="body-sm text-muted-foreground">System Prompt</span>
              <span class="body-sm font-medium text-foreground">{{
                model.configuration.system_prompt || 'Default'
              }}</span>
            </div>
          </div>
        </div>

        <!-- Connected Endpoints -->
        <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
          <h2 class="heading-3 mb-4">Connected Endpoints ({{ connectedEndpoints.length }})</h2>
          <div v-if="connectedEndpoints.length > 0" class="space-y-4">
            <div
              v-for="endpoint in connectedEndpoints"
              :key="endpoint.id"
              class="flex items-center gap-4 py-6 px-6 bg-muted/50 border border-border rounded-2xl hover:bg-muted/80 transition-all cursor-pointer"
              @click="navigateToEndpoint(endpoint.slug)"
            >
              <div class="p-3 bg-primary/10 rounded-xl">
                <Globe class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1">
                <h3 class="body-sm font-medium text-foreground">{{ endpoint.name }}</h3>
                <p class="body-sm text-muted-foreground mt-1">
                  {{ endpoint.slug || 'API endpoint' }}
                </p>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-16">
            <Globe class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p class="text-muted-foreground body-sm mb-4">No endpoints connected to this model</p>
            <Button size="sm" @click="navigateToCreateEndpoint">
              <Plus class="h-4 w-4 mr-2" />
              Create Endpoint
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Edit Model Dialog -->
  <CreateModelDialogSimple
    v-model:open="showEditDialog"
    :model="editingModel"
    @model-updated="handleModelUpdated"
    @update:open="!$event && handleEditDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <DeleteConfirmationDialog
    v-model:open="showDeleteDialog"
    item-type="Model"
    :item-name="model?.name || ''"
    :dependencies="modelDependencies"
    dependency-type="endpoint"
    @confirm="confirmDelete"
    @cancel="cancelDelete"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Brain, ChevronRight, Trash2, Globe, Plus, Edit } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import CreateModelDialogSimple from '@/components/CreateModelDialogSimple.vue'
import { formatDate } from '@/lib/formatters'
import { useNavigation } from '@/composables/useNavigation'
import { modelsApi } from '@/api/endpoints/models'
import type { ModelResponseWithEndpoints, ModelTypeInfoResponse } from '@/api/types'
import { toast } from 'vue-sonner'

// Extended interface for UI-specific properties
interface ParsedModel extends Omit<ModelResponseWithEndpoints, 'tags'> {
  tags: string[] // Converted from comma-separated string
  status: 'running' | 'stopped' // Mock status for now
  endpointCount: number
}

const route = useRoute()
const router = useRouter()
const { goToModels } = useNavigation()

const loading = ref(true)
const error = ref(false)
const model = ref<ParsedModel | null>(null)
const modelTypeInfo = ref<ModelTypeInfoResponse | null>(null)
const showDeleteDialog = ref(false)
const showEditDialog = ref(false)
const editingModel = ref<ParsedModel | null>(null)
// Dependencies for delete dialog
const modelDependencies = computed(() => {
  if (!model.value || model.value.endpointCount === 0) return []

  return model.value.connected_endpoints.map((endpoint) => ({
    id: endpoint.id,
    name: endpoint.name,
  }))
})

const connectedEndpoints = computed(() => {
  if (!model.value || !model.value.connected_endpoints) return []
  return model.value.connected_endpoints
})

const editModel = () => {
  if (model.value) {
    editingModel.value = model.value
    showEditDialog.value = true
  }
}

const deleteModel = () => {
  showDeleteDialog.value = true
}

const confirmDelete = async () => {
  if (model.value) {
    try {
      await modelsApi.delete(model.value.name)
      toast.success(`Model "${model.value.name}" deleted successfully`)
      goToModels()
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete model'
      toast.error(errorMessage)
      console.error('Delete failed:', error)
    }
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
}

const handleModelUpdated = async () => {
  showEditDialog.value = false
  editingModel.value = null
  // Reload model data
  if (model.value) {
    await loadModel(model.value.name)
  }
}

const handleEditDialogClose = () => {
  editingModel.value = null
}

const navigateToCreateEndpoint = () => {
  router.push({ name: 'create-model-endpoint' })
}

const navigateToEndpoint = (slug: string) => {
  router.push(`/endpoints/${slug}`)
}

const loadModel = async (name: string) => {
  try {
    loading.value = true
    error.value = false

    const modelResponse = await modelsApi.get(name)

    // Parse the model and convert tags string to array
    const parsedModel: ParsedModel = {
      ...modelResponse,
      tags: modelResponse.tags ? modelResponse.tags.split(',').map((tag) => tag.trim()) : [],
      status: 'stopped' as const, // Mock status for now
      endpointCount: modelResponse.connected_endpoints?.length || 0,
    }

    model.value = parsedModel

    // Fetch model type information
    try {
      const typeInfoResponse = await modelsApi.getType(modelResponse.dtype)
      modelTypeInfo.value = typeInfoResponse
    } catch (typeErr) {
      console.error('Failed to load model type info:', typeErr)
      modelTypeInfo.value = null
    }
  } catch (err) {
    console.error('Failed to load model:', err)
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const modelSlug = route.params.slug as string
  await loadModel(modelSlug)
})
</script>
