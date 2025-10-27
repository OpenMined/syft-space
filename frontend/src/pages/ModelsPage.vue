<template>
  <div class="max-w-6xl mx-auto px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Brain class="h-6 w-6 text-[var(--color-secondary)]" />
        <h1 class="text-3xl font-heading font-semibold text-[var(--color-text)]">Your Models</h1>
      </div>
      <p class="text-sm text-[var(--color-text-light)] md:max-w-[50%]">Models here are accessible only for your private use. They're ideal for building powerful flows on your machine; expose them to others later by creating endpoints.</p>
    </div>

    <!-- Header with tabs and search bar -->
    <div class="flex items-center justify-between gap-4 mb-8">
      <!-- Tabs -->
      <Tabs v-model="activeTab" class="w-auto">
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]"
        >
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="running">Running</TabsTrigger>
          <TabsTrigger value="stopped">Stopped</TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Search bar and Create button -->
      <div class="flex items-center gap-4">
        <div class="relative w-80">
          <Search
            class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400"
          />
          <Input
            v-model="searchQuery"
            placeholder="Find models, tags, types..."
            class="pl-10 pr-4 py-2.5 w-full bg-[var(--color-bg-alt)] border-[var(--color-border)] rounded-lg focus:bg-[var(--color-bg-light)] transition-colors"
          />
        </div>

        <!-- Add Model Button -->
        <Button
          class="bg-[var(--color-accent)] hover:bg-[var(--color-accent-strong)] text-white px-5 py-2.5 rounded-lg shadow-sm hover:shadow-md transition-all"
          @click="showCreateModelDialog = true"
        >
          <Plus class="h-4 w-4 mr-2" />
          Add Model
        </Button>
      </div>
    </div>

    <!-- Models List -->
    <div class="space-y-5">
      <div
        v-for="model in filteredModels"
        :key="model.id"
        class="bg-[var(--color-bg-light)] border border-[var(--color-border)] rounded-xl p-6 hover:shadow-lg transition-all cursor-pointer"
        @click="navigateToDetail(model.name)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div
              :class="[
                'p-3.5 rounded-xl',
                model.type === 'vllm'
                  ? 'bg-purple-100'
                  : model.type === 'ollama'
                    ? 'bg-orange-100'
                    : 'bg-indigo-100',
              ]"
            >
              <IntegrationIcon :name="model.type" class="h-6 w-6" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-2">
                <h3 class="text-lg font-heading font-medium text-[var(--color-text)]">{{ model.name }}</h3>
                <Badge
                  variant="outline"
                  :class="
                    model.status === 'running'
                      ? 'bg-[var(--color-success-contrast)] text-[var(--color-success-strong)] border-[var(--color-success)]'
                      : 'bg-[var(--color-bg-alt)] text-[var(--color-text-light)] border-[var(--color-border)]'
                  "
                  class="text-xs px-2.5 py-1 rounded-md"
                >
                  <div
                    :class="
                      model.status === 'running'
                        ? 'w-2 h-2 bg-green-500 rounded-full mr-1'
                        : 'w-2 h-2 bg-gray-400 rounded-full mr-1'
                    "
                  ></div>
                  {{ model.status }}
                </Badge>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Badge
                        variant="outline"
                        :class="
                          model.endpointCount > 0
                            ? 'bg-[var(--color-info-contrast)] text-[var(--color-info-strong)] border-[var(--color-info)] cursor-help'
                            : 'bg-[var(--color-bg-alt)] text-[var(--color-text-light)] border-[var(--color-border)]'
                        "
                        class="text-xs px-2.5 py-1 rounded-md"
                      >
                        <div
                          :class="
                            model.endpointCount > 0
                              ? 'w-2 h-2 bg-blue-500 rounded-full mr-1'
                              : 'w-2 h-2 bg-gray-400 rounded-full mr-1'
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
                        <p class="font-medium text-xs">Connected Endpoints:</p>
                        <ul class="space-y-1">
                          <li
                            v-for="endpointName in getEndpointNamesForModel(model.id)"
                            :key="endpointName"
                            class="text-xs"
                          >
                            • {{ endpointName }}
                          </li>
                        </ul>
                      </div>
                    </TooltipContent>
                    <TooltipContent v-else>
                      <p class="text-xs">This model is not connected to any endpoint</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p class="text-[var(--color-text-light)] mb-4">
                {{ model.description }}
              </p>
              <div class="flex gap-2">
                <Badge
                  v-for="tag in model.tags"
                  :key="tag"
                  variant="outline"
                  class="text-xs px-3 py-1 rounded-full border-[var(--color-border)] text-[var(--color-text-light)]"
                >
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              class="text-gray-600"
              @click.stop="handleEditModel(model)"
            >
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              class="text-red-600 hover:text-red-700"
              @click.stop="handleDeleteModel(model)"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- DEMO: Empty State Section -->
    <div class="mt-16">
      <!-- Divider with centered text -->
      <div class="relative">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-gray-300"></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-4 bg-gray-50 text-gray-600 font-medium">
            Demo: Empty State (shown when no models exist)
          </span>
        </div>
      </div>

      <!-- Empty state content -->
      <div class="mt-8 bg-white rounded-lg shadow border border-gray-200 p-8 text-center">
        <Brain class="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">No models yet</h3>
        <p class="text-gray-600 mb-4">Start by adding or connecting your first AI model</p>
        <Button
          class="bg-purple-600 hover:bg-purple-700 text-white"
          @click="showCreateModelDialog = true"
        >
          <Plus class="h-4 w-4 mr-2" />
          Add Model
        </Button>
      </div>
    </div>
  </div>

  <!-- Create Model Dialog -->
  <CreateModelDialog
    v-model:open="showCreateModelDialog"
    :model="editingModel"
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
          <div class="bg-red-50 border border-red-200 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-red-900 font-semibold text-sm mb-2">
                  This model has {{ modelToDelete.endpointCount }} dependent endpoint{{
                    modelToDelete.endpointCount !== 1 ? 's' : ''
                  }}
                  that will be deleted:
                </p>
                <p class="text-red-800 text-xs mb-3">Check each endpoint to confirm deletion</p>
                <div class="space-y-2">
                  <div
                    v-for="endpointName in getEndpointNamesForModel(modelToDelete.id)"
                    :key="endpointName"
                    class="flex items-center gap-3 p-2.5 bg-white rounded border border-red-200"
                  >
                    <input
                      type="checkbox"
                      :id="`endpoint-${endpointName}`"
                      :checked="checkedEndpoints.includes(endpointName)"
                      @change="() => toggleEndpoint(endpointName)"
                      class="w-4 h-4 text-red-600 bg-white border-red-400 rounded focus:ring-red-500 focus:ring-2"
                    />
                    <label
                      :for="`endpoint-${endpointName}`"
                      class="flex-1 cursor-pointer flex items-center justify-between"
                    >
                      <span class="text-sm font-medium text-gray-900">
                        {{ endpointName }}
                      </span>
                      <span class="text-xs text-red-600"> Will be deleted </span>
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
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Brain, Plus, Edit, Trash2, Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
import CreateModelDialog from '@/components/CreateModelDialog.vue'

import { mockModels, type Model } from '@/stores/models'

interface Endpoint {
  id: string
  name: string
  modelIds: string[]
}

// Mock endpoints data
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

// Use shared models data
const models = ref<Model[]>(mockModels)

const showCreateModelDialog = ref(false)
const searchQuery = ref('')
const activeTab = ref('all')
const editingModel = ref<Model | null>(null)
const showDeleteDialog = ref(false)
const modelToDelete = ref<Model | null>(null)
const checkedEndpoints = ref<string[]>([])

const filteredModels = computed(() => {
  return models.value.filter((model) => {
    // Search query filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      if (
        !model.name.toLowerCase().includes(query) &&
        !model.description.toLowerCase().includes(query) &&
        !model.tags.some((tag) => tag.toLowerCase().includes(query))
      ) {
        return false
      }
    }

    // Tab filter
    if (activeTab.value === 'running' && model.status !== 'running') {
      return false
    }
    if (activeTab.value === 'stopped' && model.status !== 'stopped') {
      return false
    }

    return true
  })
})

const handleModelCreated = () => {
  console.log('Model created successfully')
}

const handleEditModel = (model: Model) => {
  editingModel.value = model
  showCreateModelDialog.value = true
}

const handleModelUpdated = () => {
  console.log('Model updated successfully')
  editingModel.value = null
}

// Function to get endpoint names connected to a model
const getEndpointNamesForModel = (modelId: string): string[] => {
  return mockEndpoints
    .filter((endpoint) => endpoint.modelIds.includes(modelId))
    .map((endpoint) => endpoint.name)
}

// Reset editing state when dialog closes
const handleDialogClose = () => {
  editingModel.value = null
}

const handleDeleteModel = (model: Model) => {
  modelToDelete.value = model
  checkedEndpoints.value = []
  showDeleteDialog.value = true
}

const confirmDeleteModel = () => {
  if (modelToDelete.value) {
    console.log('Deleting model:', modelToDelete.value.name)
    // In a real app, this would call an API to delete the model
    const index = models.value.findIndex((m) => m.id === modelToDelete.value!.id)
    if (index > -1) {
      models.value.splice(index, 1)
    }
    showDeleteDialog.value = false
    modelToDelete.value = null
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
