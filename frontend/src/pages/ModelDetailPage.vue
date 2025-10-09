<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-6" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link 
            to="/models" 
            class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center"
          >
            <Brain class="h-4 w-4 mr-1" />
            Models
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-gray-400 mx-2" />
          <span class="text-gray-900 text-sm font-medium">{{ model?.name || 'Loading...' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Error State -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <h3 class="text-lg font-medium text-red-900 mb-2">Model not found</h3>
      <p class="text-red-700 mb-4">The model you're looking for doesn't exist or has been deleted.</p>
      <Button @click="$router.push('/models')" variant="outline">
        Back to Models
      </Button>
    </div>

    <!-- Model Details -->
    <div v-else-if="model" class="space-y-6">
      <!-- Header -->
      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div :class="[
              'p-3 rounded-lg',
              model.type === 'vllm' ? 'bg-purple-100' : 
              model.type === 'ollama' ? 'bg-orange-100' : 
              'bg-indigo-100'
            ]">
              <IntegrationIcon :name="model.type" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="text-3xl font-bold text-gray-900 mb-2">{{ model.name }}</h1>
              <p class="text-gray-600 mb-4">{{ model.description }}</p>
              <div class="flex flex-wrap items-center gap-2">
                <Badge :variant="model.status === 'running' ? 'default' : 'outline'" :class="model.status === 'running'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-gray-50 text-gray-600 border-gray-200'">
                  <div :class="model.status === 'running'
                    ? 'w-2 h-2 bg-green-500 rounded-full mr-2'
                    : 'w-2 h-2 bg-gray-400 rounded-full mr-2'"></div>
                  {{ model.status === 'running' ? 'Running' : 'Stopped' }}
                </Badge>
                <Badge variant="outline" class="bg-blue-50 text-blue-700 border-blue-200">
                  <div class="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                  {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}
                </Badge>
                <!-- Tags as badges -->
                <Badge v-for="tag in model.tags" :key="`tag-${tag}`" variant="outline"
                  class="bg-amber-50 text-amber-700 border-amber-200">
                  <div class="w-2 h-2 bg-amber-500 rounded-full mr-2"></div>
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" @click="editModel">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button variant="outline" class="text-red-600 hover:text-red-700" @click="deleteModel">
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>

      <!-- Content Grid -->
      <div class="space-y-6">
        <!-- Top Row - Equal Width Cards -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Model Details -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Model Details</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Type:</span>
                <span class="text-sm text-gray-900">{{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Status:</span>
                <span class="text-sm text-gray-900 capitalize">{{ model.status }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Connected Endpoints:</span>
                <span class="text-sm text-gray-900">{{ model.endpointCount }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Created:</span>
                <span class="text-sm text-gray-900">{{ formatDate(model.createdAt) }}</span>
              </div>
            </div>
          </div>

          <!-- Model Earnings -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Model Earnings</h2>
            <div class="space-y-4">
              <div class="text-center p-4 bg-green-50 rounded-lg">
                <p class="text-2xl font-bold text-green-600 mb-1">{{ getEarnings().total }}</p>
                <p class="text-sm text-green-700">Total Earnings</p>
              </div>
              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">This Month:</span>
                  <span class="text-sm text-green-600 font-semibold">{{ getEarnings().thisMonth }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">Growth:</span>
                  <span class="text-sm text-green-600 font-semibold">{{ getEarnings().growth }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Usage Statistics -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Usage Statistics</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Total Requests:</span>
                <span class="text-sm text-gray-900 font-semibold">{{ getUsageStats().totalRequests }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Success Rate:</span>
                <span class="text-sm text-green-600 font-semibold">{{ getUsageStats().successRate }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">This Month:</span>
                <span class="text-sm text-gray-900 font-semibold">{{ getUsageStats().thisMonth }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Active Users:</span>
                <span class="text-sm text-gray-900 font-semibold">{{ getUsageStats().activeUsers }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Model Configuration -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-2xl font-semibold text-gray-900 mb-4">Model Configuration</h2>
          <div class="min-h-[300px] flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg bg-gray-50">
            <div class="text-center">
              <p class="text-gray-500 text-lg mb-2">Configuration for {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}</p>
              <p class="text-gray-400 text-sm">Model configuration details will be displayed here</p>
            </div>
          </div>
        </div>

        <!-- Access Trends -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-2xl font-semibold text-gray-900">Access Trends</h2>
            <div class="flex items-center gap-2">
              <Button 
                v-for="period in ['Daily', 'Weekly', 'Monthly']" 
                :key="period"
                size="sm" 
                :variant="selectedPeriod === period ? 'default' : 'outline'"
                @click="selectedPeriod = period"
                class="text-xs"
              >
                {{ period }}
              </Button>
            </div>
          </div>
          <div class="h-64 flex items-center justify-center border border-dashed border-gray-300 rounded-lg bg-gray-50">
            <div class="text-center">
              <p class="text-gray-500 text-lg mb-1">{{ selectedPeriod }} Access Chart</p>
              <p class="text-gray-400 text-sm">Graph visualization will be displayed here</p>
            </div>
          </div>
        </div>

        <!-- Connected Endpoints - Full Width -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-xl font-semibold text-gray-900 mb-4">Connected Endpoints</h2>
          <div v-if="connectedEndpoints.length > 0" class="space-y-4">
            <div 
              v-for="endpoint in connectedEndpoints" 
              :key="endpoint.id"
              class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
            >
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-blue-100 rounded-md">
                    <Globe class="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 class="text-sm font-medium text-gray-900">{{ endpoint.name }}</h3>
                    <p class="text-xs text-gray-600">{{ endpoint.description || 'API endpoint' }}</p>
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  <ExternalLink class="h-3 w-3" />
                </Button>
              </div>
              
              <!-- Request Distribution for this endpoint -->
              <div class="mt-3 pt-3 border-t border-gray-100">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs text-gray-600 font-medium">Request Distribution</span>
                  <span class="text-xs text-gray-900 font-semibold">{{ getEndpointPercentage(endpoint.name) }}% of total</span>
                </div>
                <div class="flex items-center gap-3">
                  <div class="flex-1 bg-gray-200 rounded-full h-2">
                    <div 
                      class="h-2 rounded-full transition-all duration-300" 
                      :style="{ 
                        width: getEndpointPercentage(endpoint.name) + '%', 
                        backgroundColor: getEndpointColor(endpoint.name) 
                      }"
                    ></div>
                  </div>
                  <span class="text-xs text-gray-600">{{ getEndpointRequests(endpoint.name) }} requests</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-8">
            <Globe class="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 class="text-lg font-medium text-gray-900 mb-2">No endpoints connected</h3>
            <p class="text-gray-600 mb-4">This model is not currently connected to any endpoints.</p>
            <Button>
              <Plus class="h-4 w-4 mr-2" />
              Create Endpoint
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Create Model Dialog -->
  <CreateModelDialog
    v-model:open="showEditDialog"
    :model="model"
    @model-updated="handleModelUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Delete Model</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ model?.name }}"? This action cannot be undone.
        </DialogDescription>
      </DialogHeader>
      
      <div v-if="model && model.endpointCount > 0" class="py-4">
        <div class="space-y-4">
          <div class="bg-red-50 border border-red-200 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-red-900 font-semibold text-sm mb-2">
                  This model has {{ model.endpointCount }} dependent endpoint{{ model.endpointCount !== 1 ? 's' : '' }} that will be deleted:
                </p>
                <p class="text-red-800 text-xs mb-3">
                  Check each endpoint to confirm deletion
                </p>
                <div class="space-y-2">
                  <div 
                    v-for="endpointName in getEndpointNamesForModel(model.id)" 
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
                      <span class="text-xs text-red-600">
                        Will be deleted
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="cancelDelete">
          Cancel
        </Button>
        <Button 
          variant="destructive" 
          @click="confirmDelete"
          :disabled="!allEndpointsChecked"
        >
          {{ model?.endpointCount > 0 
            ? `Delete Model & ${model.endpointCount} Endpoint${model.endpointCount !== 1 ? 's' : ''}` 
            : 'Delete Model' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Brain, ChevronRight, Edit, Trash2, Globe, Plus, ExternalLink } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import { mockModels, type Model } from '@/stores/models'

interface Endpoint {
  id: string
  name: string
  description?: string
  modelIds: string[]
}

// Mock data - in a real app, this would come from an API

const mockEndpoints: Endpoint[] = [
  {
    id: 'endpoint-1',
    name: 'Document Analysis API',
    description: 'Analyze and extract insights from documents',
    modelIds: ['nlp-engine']
  },
  {
    id: 'endpoint-2', 
    name: 'Content Generation API',
    description: 'Generate content using AI models',
    modelIds: ['nlp-engine']
  },
  {
    id: 'endpoint-3',
    name: 'Code Review Assistant',
    description: 'AI-powered code review and suggestions',
    modelIds: ['code-assistant']
  }
]

const route = useRoute()
const router = useRouter()

const error = ref(false)
const model = ref<Model | null>(null)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const checkedEndpoints = ref<string[]>([])
const selectedPeriod = ref('Daily')

const connectedEndpoints = computed(() => {
  if (!model.value) return []
  return mockEndpoints.filter(endpoint => 
    endpoint.modelIds.includes(model.value!.id)
  )
})

const formatDate = (date: Date) => {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const getUsageStats = () => {
  // Mock data - in real app this would come from analytics API
  return {
    totalRequests: '23.7k',
    successRate: '97.3%',
    thisMonth: '5.2k',
    activeUsers: '156'
  }
}

const getEarnings = () => {
  // Mock data - in real app this would come from billing/revenue API
  return {
    total: '$1,247.85',
    thisMonth: '$312.40',
    lastMonth: '$289.15',
    avgPerRequest: '$0.053',
    growth: '+8.1%'
  }
}

const getEndpointDistribution = () => {
  // Mock data - in real app this would come from analytics API
  return [
    { name: 'Document Analysis API', percentage: 65, color: '#3B82F6', requests: '15.4k' },
    { name: 'Content Generation API', percentage: 35, color: '#10B981', requests: '8.3k' }
  ]
}

const getEndpointPercentage = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find(e => e.name === endpointName)
  return endpoint?.percentage || 0
}

const getEndpointColor = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find(e => e.name === endpointName)
  return endpoint?.color || '#6B7280'
}

const getEndpointRequests = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find(e => e.name === endpointName)
  return endpoint?.requests || '0'
}


// Function to get endpoint names connected to a model
const getEndpointNamesForModel = (modelId: string): string[] => {
  return mockEndpoints
    .filter(endpoint => endpoint.modelIds.includes(modelId))
    .map(endpoint => endpoint.name)
}

// Check if all endpoints are selected
const allEndpointsChecked = computed(() => {
  if (!model.value) return true
  if (model.value.endpointCount === 0) return true
  
  const endpointNames = getEndpointNamesForModel(model.value.id)
  return endpointNames.length > 0 && endpointNames.length === checkedEndpoints.value.length
})

// Toggle endpoint checkbox
const toggleEndpoint = (endpointName: string) => {
  const index = checkedEndpoints.value.indexOf(endpointName)
  if (index > -1) {
    checkedEndpoints.value.splice(index, 1)
  } else {
    checkedEndpoints.value.push(endpointName)
  }
}

const editModel = () => {
  showEditDialog.value = true
}

const deleteModel = () => {
  checkedEndpoints.value = []
  showDeleteDialog.value = true
}

const handleModelUpdated = () => {
  console.log('Model updated successfully')
  showEditDialog.value = false
  // In a real app, you might want to refresh the model data here
}

const handleDialogClose = () => {
  showEditDialog.value = false
}

const confirmDelete = () => {
  if (model.value) {
    console.log('Deleting model:', model.value.name)
    // In a real app, this would call an API to delete the model
    // Then navigate back to the list
    router.push('/models')
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  checkedEndpoints.value = []
}

onMounted(() => {
  const modelSlug = route.params.slug as string
  const foundModel = mockModels.find(m => m.name === modelSlug)
  
  if (foundModel) {
    model.value = foundModel
  } else {
    error.value = true
  }
})
</script>